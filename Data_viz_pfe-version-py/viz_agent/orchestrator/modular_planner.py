from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from viz_agent.orchestrator.base_agent import BaseAgent
from viz_agent.orchestrator.deterministic_fallbacks import DeterministicFallbackEngine
from viz_agent.orchestrator.heuristic_fallbacks import HeuristicFallbackEngine
from viz_agent.orchestrator.llm_fallbacks import LLMFallbackCorrectionEngine
from viz_agent.orchestrator.llm_self_evaluator import LLMSelfEvaluator
from viz_agent.orchestrator.modular_agents import (
    ParsingAgent,
    RDLAgent,
    RuntimeValidationAgent,
    SemanticAgent,
    TransformationAgent,
    ValidationAgent,
    VisualizationAgent,
)
from viz_agent.orchestrator.phase_cache_store import PhaseCacheStore
from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.pipeline_context import PipelineContext
from viz_agent.orchestrator.validation_gates import ValidationGates


@dataclass
class PlannerRunResult:
    status: str
    phase_results: dict[str, PhaseAgentResult] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class PlannerAgent:
    """Modular planner with retries, fallback chain, gates, cache and trace hooks."""

    def __init__(
        self,
        agents: list[BaseAgent] | None = None,
        gates: ValidationGates | None = None,
        max_retries: int = 2,
        stop_on_error: bool = True,
        trace_file: Path | None = None,
        debug_snapshot_dir: Path | None = None,
        enable_phase_cache: bool = True,
        cache_dir: Path | None = None,
        enable_llm_fallback: bool | None = None,
        enable_llm_self_eval: bool | None = None,
        deterministic_fallbacks: DeterministicFallbackEngine | None = None,
        heuristic_fallbacks: HeuristicFallbackEngine | None = None,
        llm_fallbacks: LLMFallbackCorrectionEngine | None = None,
        self_evaluator: LLMSelfEvaluator | None = None,
    ) -> None:
        self.agents = agents or [
            ParsingAgent(),
            SemanticAgent(),
            VisualizationAgent(),
            TransformationAgent(),
            RDLAgent(),
            RuntimeValidationAgent(),
        ]
        self._agents_by_name = {agent.name: agent for agent in self.agents}
        self.gates = gates or ValidationGates()
        self.validation_agent = ValidationAgent(self.gates)
        self.max_retries = max(0, int(max_retries))
        self.stop_on_error = bool(stop_on_error)
        self.trace_file = trace_file
        self.debug_snapshot_dir = debug_snapshot_dir
        self._enable_phase_cache = bool(enable_phase_cache)
        resolved_cache_dir = cache_dir or ((trace_file.parent / ".viz_agent_cache") if trace_file is not None else (Path.cwd() / ".viz_agent_cache"))
        self._phase_cache = PhaseCacheStore(resolved_cache_dir)
        self._deterministic_fallbacks = deterministic_fallbacks or DeterministicFallbackEngine()
        self._heuristic_fallbacks = heuristic_fallbacks or HeuristicFallbackEngine()
        self._llm_fallbacks = llm_fallbacks or LLMFallbackCorrectionEngine(enabled=enable_llm_fallback)
        self._self_evaluator = self_evaluator or LLMSelfEvaluator(enabled=enable_llm_self_eval)

    def run(self, context: PipelineContext) -> PlannerRunResult:
        if not context.execution_id:
            context.execution_id = f"modular_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        run_result = PlannerRunResult(status="success")

        for agent in self.agents:
            context.set_phase(agent.name)
            self._trace("phase_start", context, {"phase": agent.name})

            phase_fingerprint = self._compute_phase_fingerprint(context, agent.name)
            if self._enable_phase_cache:
                cached = self._phase_cache.get(agent.name, phase_fingerprint)
                if cached is not None and isinstance(cached.result, dict):
                    cached_result = PhaseAgentResult(**cached.result).normalized()
                    context.update_from_phase_result(agent.name, cached_result.output, cached_result.confidence)
                    run_result.phase_results[agent.name] = cached_result
                    run_result.retries[agent.name] = 0
                    self._trace(
                        "cache_hit",
                        context,
                        {
                            "phase": agent.name,
                            "fingerprint": phase_fingerprint,
                            "artifact_paths": dict(cached.artifact_paths),
                        },
                    )
                    self._snapshot(context, f"phase_{agent.name}_cache_hit")
                    self._trace("phase_end", context, {"phase": agent.name, "status": cached_result.status})
                    continue

            attempts = 0
            phase_result = PhaseAgentResult(status="error", confidence=0.0, errors=["not executed"]).normalized()

            while attempts <= self.max_retries:
                attempt = attempts + 1
                thought = f"Need reliable output for {agent.name}; attempt {attempt}."
                action = f"execute_tool:{agent.name}"
                self._trace("react_thought", context, {"phase": agent.name, "attempt": attempt, "thought": thought})
                if agent.name == "runtime_validation":
                    self._trace("runtime_validation_started", context, {"phase": agent.name, "attempt": attempt})

                phase_result = agent.execute(context).normalized()
                gate_ok, gate_issues = self._validate_phase(agent.name, phase_result.output)
                if gate_issues:
                    for issue in gate_issues:
                        context.add_error(agent.name, issue)

                if phase_result.status != "error" and agent.name in {"specification", "export"}:
                    eval_result = (
                        self._self_evaluator.evaluate_phase3(phase_result.output)
                        if agent.name == "specification"
                        else self._self_evaluator.evaluate_phase5(phase_result.output)
                    )
                    self._trace(
                        "llm_self_eval",
                        context,
                        {
                            "phase": agent.name,
                            "attempt": attempt,
                            "score": eval_result.score,
                            "issues": list(eval_result.issues),
                            "dimensions": dict(eval_result.dimensions),
                            "provider": eval_result.provider,
                        },
                    )
                    if self._self_evaluator.is_below_threshold(agent.name, eval_result):
                        phase_result = PhaseAgentResult(
                            status="error",
                            confidence=min(phase_result.confidence, float(eval_result.score)),
                            output=phase_result.output,
                            errors=list(phase_result.errors) + [f"Self-eval score too low ({eval_result.score:.2f})"] + list(eval_result.issues),
                            retry_hint="Self-eval below threshold; retry with corrections.",
                        ).normalized()

                observation = (
                    f"attempt={attempt}, status={phase_result.status}, "
                    f"confidence={phase_result.confidence:.2f}, errors={len(phase_result.errors)}"
                )
                context.add_react_event(thought, action, observation, agent.name, attempt)
                context.record_confidence(agent.name, phase_result.confidence, phase_result.status)
                self._trace(
                    "react_observation",
                    context,
                    {
                        "phase": agent.name,
                        "attempt": attempt,
                        "result": asdict(phase_result),
                    },
                )
                if agent.name == "runtime_validation":
                    self._trace(
                        "runtime_validation_success" if phase_result.status == "success" and gate_ok else "runtime_validation_failed",
                        context,
                        {
                            "phase": agent.name,
                            "attempt": attempt,
                            "status": phase_result.status,
                            "confidence": phase_result.confidence,
                            "errors": list(phase_result.errors),
                        },
                    )
                    self._route_runtime_errors(context, run_result, phase_result)

                if phase_result.status == "success" and gate_ok:
                    break

                decision = self._decision_for(phase_result)
                self._trace("phase_decision", context, {"phase": agent.name, "attempt": attempt, "decision": decision})

                # Fallback priority chain: deterministic > heuristic > llm.
                dfix = self._deterministic_fallbacks.apply(agent.name, context.to_state_dict(), phase_result.errors)
                self._trace(
                    "deterministic_fix",
                    context,
                    {
                        "phase": agent.name,
                        "attempt": attempt,
                        "applied": dfix.applied,
                        "fix_name": dfix.fix_name,
                        "notes": list(dfix.notes),
                    },
                )
                hfix = self._heuristic_fallbacks.apply(agent.name, context.to_state_dict(), phase_result.errors, attempt=attempt)
                self._trace(
                    "heuristic_fix",
                    context,
                    {
                        "phase": agent.name,
                        "attempt": attempt,
                        "applied": hfix.applied,
                        "fix_name": hfix.fix_name,
                        "notes": list(hfix.notes),
                    },
                )
                if attempt >= 2:
                    lfix = self._llm_fallbacks.apply(agent.name, context.to_state_dict(), phase_result.errors, attempt=attempt)
                    self._trace(
                        "llm_fix",
                        context,
                        {
                            "phase": agent.name,
                            "attempt": attempt,
                            "applied": lfix.applied,
                            "fix_name": lfix.fix_name,
                            "notes": list(lfix.notes),
                        },
                    )

                attempts += 1
                if attempts > self.max_retries:
                    break
                self._snapshot(context, f"phase_{agent.name}_retry_attempt{attempt}")

            run_result.phase_results[agent.name] = phase_result
            run_result.retries[agent.name] = attempts

            if self._enable_phase_cache and phase_result.status == "success":
                cached = self._phase_cache.set(agent.name, phase_fingerprint, asdict(phase_result))
                self._trace(
                    "cache_write",
                    context,
                    {
                        "phase": agent.name,
                        "fingerprint": phase_fingerprint,
                        "artifact_paths": dict(cached.artifact_paths),
                    },
                )

            if phase_result.status != "success":
                run_result.errors.extend([f"{agent.name}: {e}" for e in phase_result.errors])
                run_result.status = "failed"
                self._snapshot(context, f"phase_{agent.name}_failed")
                self._trace("phase_end", context, {"phase": agent.name, "status": phase_result.status})
                if self.stop_on_error:
                    break

            gate_ok, gate_issues = self._validate_phase(agent.name, phase_result.output)
            if not gate_ok:
                run_result.errors.extend([f"{agent.name}: {issue}" for issue in gate_issues])
                run_result.status = "failed"
                self._trace("phase_end", context, {"phase": agent.name, "status": "error"})
                if self.stop_on_error:
                    break

            self._snapshot(context, f"phase_{agent.name}_accepted")
            self._trace("phase_end", context, {"phase": agent.name, "status": phase_result.status})

        context.set_phase(self.validation_agent.name)
        validation = self.validation_agent.execute(context).normalized()
        run_result.phase_results[self.validation_agent.name] = validation
        run_result.retries[self.validation_agent.name] = 0
        if validation.status != "success":
            run_result.status = "failed"
            run_result.errors.extend([f"validation: {e}" for e in validation.errors])
        self._trace("phase_end", context, {"phase": self.validation_agent.name, "status": validation.status})

        return run_result

    @staticmethod
    def _decision_for(result: PhaseAgentResult) -> str:
        if result.status == "success" and result.confidence > 0.8:
            return "accept"
        if result.status in {"success", "low_confidence"} and 0.5 < result.confidence < 0.8:
            return "retry_heuristic"
        return "fallback"

    def _validate_phase(self, phase_name: str, output: dict[str, Any]) -> tuple[bool, list[str]]:
        # Only these phases have deterministic gate definitions.
        if phase_name not in {"parsing", "semantic_reasoning", "specification", "export", "runtime_validation"}:
            return True, []

        gate = self.gates.validate(phase_name, output if isinstance(output, dict) else {})
        return gate.passed, list(gate.issues)

    def _route_runtime_errors(self, context: PipelineContext, run_result: PlannerRunResult, phase_result: PhaseAgentResult) -> None:
        if phase_result.status == "success":
            return

        runtime_payload = phase_result.output.get("runtime_validation") if isinstance(phase_result.output, dict) else {}
        runtime_errors = runtime_payload.get("errors") if isinstance(runtime_payload, dict) else []
        if not isinstance(runtime_errors, list):
            return

        for err in runtime_errors:
            err_d = err if isinstance(err, dict) else {}
            err_type = str(err_d.get("type") or "").lower()
            target = self._target_agent_for_runtime_error(err_type)
            self._trace(
                "runtime_error_detected",
                context,
                {
                    "error_type": err_type,
                    "message": str(err_d.get("message") or ""),
                    "location": str(err_d.get("location") or ""),
                    "severity": str(err_d.get("severity") or ""),
                    "target_agent": target,
                },
            )
            if not target:
                continue
            target_agent = self._agents_by_name.get(target)
            if target_agent is None:
                continue

            context.set_phase(target_agent.name)
            repaired = target_agent.execute(context).normalized()
            run_result.phase_results[target_agent.name] = repaired
            run_result.retries[target_agent.name] = run_result.retries.get(target_agent.name, 0) + 1
            if repaired.status != "success":
                run_result.errors.extend([f"{target_agent.name}: {e}" for e in repaired.errors])

    @staticmethod
    def _target_agent_for_runtime_error(error_type: str) -> str:
        if error_type == "schema_error":
            return "export"
        if error_type == "datasource_error":
            return "semantic_reasoning"
        if error_type == "rendering_error":
            return "specification"
        return ""

    def _trace(self, event: str, context: PipelineContext, payload: dict[str, Any]) -> None:
        if self.trace_file is None:
            return
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "execution_id": context.execution_id,
            "current_phase": context.current_phase,
            "payload": payload,
        }
        with self.trace_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _snapshot(self, context: PipelineContext, label: str) -> None:
        if self.debug_snapshot_dir is None:
            return
        path = context.snapshot(self.debug_snapshot_dir, label)
        self._trace("snapshot", context, {"path": str(path), "label": label})

    def _compute_phase_fingerprint(self, context: PipelineContext, phase_name: str) -> str:
        dependencies = {
            "parsing": ["artifacts", "runtime_context.intent", "previous_outputs.data_extraction"],
            "semantic_reasoning": ["runtime_context.intent", "previous_outputs.data_extraction", "previous_outputs.parsing"],
            "specification": ["runtime_context.intent", "previous_outputs.semantic_reasoning"],
            "transformation": ["runtime_context.intent", "previous_outputs.specification"],
            "export": ["runtime_context.intent", "previous_outputs.transformation"],
            "runtime_validation": ["artifacts", "previous_outputs.export"],
        }
        selected = {"phase": phase_name, "deps": {}}
        for dep in dependencies.get(phase_name, ["artifacts", "runtime_context.intent", "previous_outputs"]):
            selected["deps"][dep] = self._extract_dep(context, dep)
        return self._phase_cache.compute_fingerprint(phase_name, selected)

    @staticmethod
    def _extract_dep(context: PipelineContext, dep: str) -> Any:
        cursor: Any = {
            "artifacts": context.artifacts,
            "runtime_context": context.runtime_context,
            "previous_outputs": context.previous_outputs,
        }
        for token in dep.split("."):
            if isinstance(cursor, dict):
                cursor = cursor.get(token)
            else:
                return None
        return cursor
