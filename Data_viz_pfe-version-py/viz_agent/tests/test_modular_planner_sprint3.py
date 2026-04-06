from __future__ import annotations

import json

from viz_agent.orchestrator.modular_planner import PlannerAgent
from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.pipeline_context import PipelineContext


class _RecordingDeterministic:
    def __init__(self):
        self.calls: list[str] = []

    def apply(self, phase_name, state, errors):
        self.calls.append(f"det:{phase_name}")
        return type("Fix", (), {"applied": True, "fix_name": "det", "notes": []})()


class _RecordingHeuristic:
    def __init__(self):
        self.calls: list[str] = []

    def apply(self, phase_name, state, errors, *, attempt):
        self.calls.append(f"heu:{phase_name}:{attempt}")
        return type("Fix", (), {"applied": True, "fix_name": "heu", "notes": []})()


class _RecordingLLM:
    def __init__(self):
        self.calls: list[str] = []

    def apply(self, phase_name, state, errors, *, attempt):
        self.calls.append(f"llm:{phase_name}:{attempt}")
        return type("Fix", (), {"applied": False, "fix_name": "llm", "notes": []})()


class _NoopSelfEval:
    def evaluate_phase3(self, output):
        return type("Eval", (), {"score": 1.0, "issues": [], "dimensions": {}, "provider": "test"})()

    def evaluate_phase5(self, output):
        return type("Eval", (), {"score": 1.0, "issues": [], "dimensions": {}, "provider": "test"})()

    def is_below_threshold(self, phase_name, result):
        return False


class _FakeAgent:
    def __init__(self, name: str, sequence: list[PhaseAgentResult]):
        self.name = name
        self._sequence = list(sequence)
        self.calls = 0

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        idx = min(self.calls, len(self._sequence) - 1)
        self.calls += 1
        result = self._sequence[idx].normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        return result


def _spec_output() -> dict:
    return {
        "abstract_spec": {
            "dashboard_spec": {
                "pages": [
                    {
                        "visuals": [
                            {
                                "type": "columnchart",
                                "data_binding": {"axes": {"x": "Category", "y": "Sales"}},
                            }
                        ]
                    }
                ]
            }
        }
    }


def test_sprint3_planner_enforces_fallback_priority(tmp_path) -> None:
    det = _RecordingDeterministic()
    heu = _RecordingHeuristic()
    llm = _RecordingLLM()

    parsing = _FakeAgent(
        "parsing",
        [
            PhaseAgentResult(status="low_confidence", confidence=0.6, output={"parsed_structure": {}}),
            PhaseAgentResult(status="success", confidence=0.9, output={"parsed_structure": {"worksheets": [{"name": "ws1"}]}}),
        ],
    )
    semantic = _FakeAgent("semantic_reasoning", [PhaseAgentResult(status="success", confidence=0.9, output={"semantic_graph": {"columns": []}})])
    spec = _FakeAgent("specification", [PhaseAgentResult(status="success", confidence=0.9, output=_spec_output())])
    transform = _FakeAgent("transformation", [PhaseAgentResult(status="success", confidence=0.9, output={"tool_model": {"datasets": []}})])
    export = _FakeAgent("export", [PhaseAgentResult(status="success", confidence=0.9, output={"export_result": {"validation": {"is_valid": True}, "content_bytes": 100}})])

    trace = tmp_path / "trace.jsonl"
    planner = PlannerAgent(
        agents=[parsing, semantic, spec, transform, export],
        trace_file=trace,
        cache_dir=tmp_path / "cache",
        deterministic_fallbacks=det,
        heuristic_fallbacks=heu,
        llm_fallbacks=llm,
        self_evaluator=_NoopSelfEval(),
        max_retries=2,
    )

    ctx = PipelineContext(execution_id="s3_test", runtime_context={"intent": {"type": "conversion"}}, artifacts={"source_path": "demo.twbx"})
    result = planner.run(ctx)

    assert result.status == "success"
    assert det.calls[0] == "det:parsing"
    assert heu.calls[0] == "heu:parsing:1"
    assert llm.calls == []

    lines = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = [line.get("event") for line in lines]
    assert "react_thought" in events
    assert "react_observation" in events
    assert "deterministic_fix" in events
    assert "heuristic_fix" in events


def test_sprint3_planner_cache_compatibility(tmp_path) -> None:
    parsing = _FakeAgent("parsing", [PhaseAgentResult(status="success", confidence=0.9, output={"parsed_structure": {"worksheets": [{"name": "ws1"}]}})])
    semantic = _FakeAgent("semantic_reasoning", [PhaseAgentResult(status="success", confidence=0.9, output={"semantic_graph": {"columns": []}})])
    spec = _FakeAgent("specification", [PhaseAgentResult(status="success", confidence=0.9, output=_spec_output())])
    transform = _FakeAgent("transformation", [PhaseAgentResult(status="success", confidence=0.9, output={"tool_model": {"datasets": []}})])
    export = _FakeAgent("export", [PhaseAgentResult(status="success", confidence=0.9, output={"export_result": {"validation": {"is_valid": True}, "content_bytes": 100}})])

    cache_dir = tmp_path / "cache"
    planner = PlannerAgent(
        agents=[parsing, semantic, spec, transform, export],
        cache_dir=cache_dir,
        self_evaluator=_NoopSelfEval(),
        max_retries=0,
    )

    ctx1 = PipelineContext(execution_id="run1", runtime_context={"intent": {"type": "conversion"}}, artifacts={"source_path": "demo.twbx"})
    result1 = planner.run(ctx1)
    assert result1.status == "success"

    calls_after_first = {
        "parsing": parsing.calls,
        "semantic": semantic.calls,
        "spec": spec.calls,
        "transform": transform.calls,
        "export": export.calls,
    }

    ctx2 = PipelineContext(execution_id="run2", runtime_context={"intent": {"type": "conversion"}}, artifacts={"source_path": "demo.twbx"})
    result2 = planner.run(ctx2)
    assert result2.status == "success"

    assert parsing.calls == calls_after_first["parsing"]
    assert semantic.calls == calls_after_first["semantic"]
    assert spec.calls == calls_after_first["spec"]
    assert transform.calls == calls_after_first["transform"]
    assert export.calls == calls_after_first["export"]
