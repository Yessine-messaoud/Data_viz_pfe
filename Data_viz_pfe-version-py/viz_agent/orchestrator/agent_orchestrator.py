from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from viz_agent.orchestrator.agent_state import AgentState
from viz_agent.orchestrator.deterministic_fallbacks import DeterministicFallbackEngine
from viz_agent.orchestrator.heuristic_fallbacks import HeuristicFallbackEngine
from viz_agent.orchestrator.llm_fallbacks import LLMFallbackCorrectionEngine
from viz_agent.orchestrator.llm_self_evaluator import LLMSelfEvaluator
from viz_agent.orchestrator.phase_agent import PhaseAgent, PhaseAgentResult
from viz_agent.orchestrator.phase_cache_store import PhaseCacheStore
from viz_agent.orchestrator.phase_tool_agents import build_default_phase_tools
from viz_agent.orchestrator.validation_gates import ValidationGates


class AgentOrchestrator:
    """Central leader agent implementing a ReAct execution loop over phase tools."""

    def __init__(
        self,
        *,
        max_retries: int = 2,
        trace_file: Path | None = None,
        debug_snapshot_dir: Path | None = None,
        enable_llm_fallback: bool | None = None,
        enable_llm_self_eval: bool | None = None,
        enable_phase_cache: bool = True,
        cache_dir: Path | None = None,
    ) -> None:
        self.max_retries = max(0, int(max_retries))
        self.trace_file = trace_file
        self.debug_snapshot_dir = debug_snapshot_dir
        self._tools: dict[str, PhaseAgent] = {}
        self._gates = ValidationGates()
        self._deterministic_fallbacks = DeterministicFallbackEngine()
        self._heuristic_fallbacks = HeuristicFallbackEngine()
        self._llm_fallbacks = LLMFallbackCorrectionEngine(enabled=enable_llm_fallback)
        self._self_evaluator = LLMSelfEvaluator(enabled=enable_llm_self_eval)
        self._enable_phase_cache = bool(enable_phase_cache)
        resolved_cache_dir = cache_dir or ((trace_file.parent / ".viz_agent_cache") if trace_file is not None else (Path.cwd() / ".viz_agent_cache"))
        self._phase_cache = PhaseCacheStore(resolved_cache_dir)

    def register_tool(self, tool: PhaseAgent) -> None:
        self._tools[tool.name] = tool

    def register_default_phase_tools(self) -> None:
        for tool in build_default_phase_tools():
            self.register_tool(tool)

    def run_conversion_flow(self, state: AgentState) -> dict[str, PhaseAgentResult]:
        ordered = [
            "data_extraction",
            "parsing",
            "semantic_reasoning",
            "specification",
            "transformation",
            "export",
        ]
        return self.run(state, ordered)

    def run(self, state: AgentState, phase_order: list[str]) -> dict[str, PhaseAgentResult]:
        results: dict[str, PhaseAgentResult] = {}

        for phase_name in phase_order:
            if phase_name not in self._tools:
                err = f"Unknown phase tool: {phase_name}"
                state.record_error(phase_name, err, attempt=0)
                self._trace("phase_missing", state, {"phase": phase_name, "error": err})
                raise ValueError(err)

            tool = self._tools[phase_name]
            state.set_phase(phase_name)
            self._trace("phase_start", state, {"phase": phase_name})

            cache_fingerprint = self._compute_phase_fingerprint(state, phase_name)
            if self._enable_phase_cache:
                cached = self._phase_cache.get(phase_name, cache_fingerprint)
                if cached is not None and isinstance(cached.result, dict):
                    cached_result = PhaseAgentResult(**cached.result).normalized()
                    state.record_output(phase_name, cached_result.output)
                    state.context.setdefault("cached_artifacts", {})[phase_name] = dict(cached.artifact_paths)
                    results[phase_name] = cached_result
                    self._trace(
                        "cache_hit",
                        state,
                        {
                            "phase": phase_name,
                            "fingerprint": cache_fingerprint,
                            "artifact_paths": dict(cached.artifact_paths),
                        },
                    )
                    self._snapshot(state, f"phase_{phase_name}_cache_hit")
                    continue

            attempt = 0
            last_result = PhaseAgentResult(status="error", confidence=0.0, errors=["No attempt executed"]) 

            while attempt <= self.max_retries:
                attempt += 1
                thought = self._build_thought(phase_name, attempt)
                action = f"execute_tool:{phase_name}"
                self._trace("react_thought", state, {"phase": phase_name, "attempt": attempt, "thought": thought})

                try:
                    raw_result = tool.execute(state.to_dict())
                    result = raw_result.normalized()
                except Exception as exc:
                    result = PhaseAgentResult(
                        status="error",
                        confidence=0.0,
                        output={},
                        errors=[str(exc)],
                        retry_hint="Agent execution exception",
                    )

                gate = self._gates.validate(phase_name, result.output)
                if not gate.passed:
                    gate_errors = [str(issue) for issue in gate.issues]
                    result = PhaseAgentResult(
                        status="error",
                        confidence=min(result.confidence, 0.49),
                        output=result.output,
                        errors=list(result.errors) + gate_errors,
                        retry_hint="Validation gate failed; apply deterministic fix and retry.",
                    ).normalized()
                    self._trace(
                        "validation_gate_failed",
                        state,
                        {
                            "phase": phase_name,
                            "attempt": attempt,
                            "issues": gate_errors,
                        },
                    )

                if phase_name in {"specification", "export"} and result.status != "error":
                    eval_result = (
                        self._self_evaluator.evaluate_phase3(result.output)
                        if phase_name == "specification"
                        else self._self_evaluator.evaluate_phase5(result.output)
                    )
                    self._trace(
                        "llm_self_eval",
                        state,
                        {
                            "phase": phase_name,
                            "attempt": attempt,
                            "score": eval_result.score,
                            "issues": list(eval_result.issues),
                            "dimensions": dict(eval_result.dimensions),
                            "provider": eval_result.provider,
                        },
                    )
                    if self._self_evaluator.is_below_threshold(phase_name, eval_result):
                        issues = [f"Self-eval score too low ({eval_result.score:.2f})"] + list(eval_result.issues)
                        result = PhaseAgentResult(
                            status="error",
                            confidence=min(result.confidence, float(eval_result.score)),
                            output=result.output,
                            errors=list(result.errors) + issues,
                            retry_hint="LLM self-eval below threshold; retry with corrections.",
                        ).normalized()

                observation = self._build_observation(result, attempt)
                state.add_react_event(thought, action, observation, phase_name, attempt)
                state.record_confidence(phase_name, result.confidence, result.status)
                if result.errors:
                    state.record_error(phase_name, "; ".join(result.errors), attempt)
                self._trace(
                    "react_observation",
                    state,
                    {
                        "phase": phase_name,
                        "attempt": attempt,
                        "result": asdict(result),
                    },
                )

                last_result = result
                decision = self._decision_for(result)
                self._trace(
                    "phase_decision",
                    state,
                    {
                        "phase": phase_name,
                        "attempt": attempt,
                        "decision": decision,
                    },
                )

                if decision == "accept":
                    state.record_output(phase_name, result.output)
                    results[phase_name] = result
                    if self._enable_phase_cache:
                        cached = self._phase_cache.set(phase_name, cache_fingerprint, asdict(result))
                        state.context.setdefault("cached_artifacts", {})[phase_name] = dict(cached.artifact_paths)
                        self._trace(
                            "cache_write",
                            state,
                            {
                                "phase": phase_name,
                                "fingerprint": cache_fingerprint,
                                "artifact_paths": dict(cached.artifact_paths),
                            },
                        )
                    self._snapshot(state, f"phase_{phase_name}_accepted")
                    break

                if decision in {"retry_heuristic", "fallback"} and attempt <= self.max_retries:
                    fix = self._deterministic_fallbacks.apply(phase_name, state.__dict__, result.errors)
                    self._trace(
                        "deterministic_fix",
                        state,
                        {
                            "phase": phase_name,
                            "attempt": attempt,
                            "applied": fix.applied,
                            "fix_name": fix.fix_name,
                            "notes": fix.notes,
                        },
                    )
                    hfix = self._heuristic_fallbacks.apply(
                        phase_name,
                        state.__dict__,
                        result.errors,
                        attempt=attempt,
                    )
                    self._trace(
                        "heuristic_fix",
                        state,
                        {
                            "phase": phase_name,
                            "attempt": attempt,
                            "applied": hfix.applied,
                            "fix_name": hfix.fix_name,
                            "notes": hfix.notes,
                        },
                    )
                    if attempt >= 2:
                        lfix = self._llm_fallbacks.apply(
                            phase_name,
                            state.__dict__,
                            result.errors,
                            attempt=attempt,
                        )
                        self._trace(
                            "llm_fix",
                            state,
                            {
                                "phase": phase_name,
                                "attempt": attempt,
                                "applied": lfix.applied,
                                "fix_name": lfix.fix_name,
                                "notes": lfix.notes,
                            },
                        )
                    self._snapshot(state, f"phase_{phase_name}_{decision}_attempt{attempt}")
                    continue

                results[phase_name] = last_result
                self._snapshot(state, f"phase_{phase_name}_failed")
                raise RuntimeError(
                    f"Phase {phase_name} failed after {attempt} attempts. "
                    f"status={last_result.status}, confidence={last_result.confidence:.2f}"
                )

            self._trace("phase_end", state, {"phase": phase_name, "status": results[phase_name].status})

        return results

    def _decision_for(self, result: PhaseAgentResult) -> str:
        if result.status == "success" and result.confidence > 0.8:
            return "accept"
        if result.status in {"success", "low_confidence"} and 0.5 < result.confidence < 0.8:
            return "retry_heuristic"
        return "fallback"

    @staticmethod
    def _build_thought(phase_name: str, attempt: int) -> str:
        return f"Need a reliable output for {phase_name}; executing attempt {attempt}."

    @staticmethod
    def _build_observation(result: PhaseAgentResult, attempt: int) -> str:
        return (
            f"attempt={attempt}, status={result.status}, "
            f"confidence={result.confidence:.2f}, errors={len(result.errors)}"
        )

    def _trace(self, event: str, state: AgentState, payload: dict[str, Any]) -> None:
        if self.trace_file is None:
            return
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "execution_id": state.execution_id,
            "current_phase": state.current_phase,
            "payload": payload,
        }
        with self.trace_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _snapshot(self, state: AgentState, label: str) -> None:
        if self.debug_snapshot_dir is None:
            return
        path = state.snapshot(self.debug_snapshot_dir, label)
        self._trace("snapshot", state, {"path": str(path), "label": label})

    def _compute_phase_fingerprint(self, state: AgentState, phase_name: str) -> str:
        dependencies = {
            "data_extraction": ["artifacts", "context.intent"],
            "parsing": ["artifacts", "context.intent", "previous_outputs.data_extraction"],
            "semantic_reasoning": ["context.intent", "previous_outputs.data_extraction", "previous_outputs.parsing"],
            "specification": ["context.intent", "previous_outputs.semantic_reasoning"],
            "transformation": ["context.intent", "previous_outputs.specification"],
            "export": ["context.intent", "previous_outputs.transformation"],
        }
        selected = {
            "phase": phase_name,
            "deps": {},
        }
        for dep in dependencies.get(phase_name, ["artifacts", "context.intent", "previous_outputs"]):
            selected["deps"][dep] = self._extract_dep(state, dep)
        return self._phase_cache.compute_fingerprint(phase_name, selected)

    @staticmethod
    def _extract_dep(state: AgentState, dep: str) -> Any:
        cursor: Any = {
            "artifacts": state.artifacts,
            "context": state.context,
            "previous_outputs": state.previous_outputs,
        }
        for token in dep.split("."):
            if isinstance(cursor, dict):
                cursor = cursor.get(token)
            else:
                return None
        return cursor
