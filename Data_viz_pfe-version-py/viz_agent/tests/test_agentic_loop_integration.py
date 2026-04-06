from __future__ import annotations

from pathlib import Path

import pytest

from viz_agent.orchestrator.agent_orchestrator import AgentOrchestrator
from viz_agent.orchestrator.agent_state import AgentState
from viz_agent.orchestrator.llm_self_evaluator import SelfEvalResult
from viz_agent.orchestrator.phase_agent import PhaseAgentResult


class _Tool:
    def __init__(self, name: str):
        self.name = name
        self.calls = 0

    def execute(self, state: dict):  # pragma: no cover - overridden
        raise NotImplementedError


class _Phase0Tool(_Tool):
    def __init__(self) -> None:
        super().__init__("data_extraction")

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(status="success", confidence=0.95, output={"metadata": {"tables": [{"name": "sales"}]}})


class _Phase1Tool(_Tool):
    def __init__(self) -> None:
        super().__init__("parsing")

    def execute(self, state: dict):
        self.calls += 1
        ctx = state.get("context", {}) if isinstance(state, dict) else {}
        dfix = ((ctx.get("deterministic_fixes") or {}).get("parsing") or {})
        if dfix.get("ensure_worksheets_from_visuals"):
            return PhaseAgentResult(
                status="success",
                confidence=0.9,
                output={"parsed_structure": {"worksheets": [{"name": "ws1"}], "visuals": [{"source_worksheet": "ws1"}], "dashboards": [{"name": "d1"}]}},
            )
        # Gate failure at first try: no valid worksheets and no source_worksheet.
        return PhaseAgentResult(status="success", confidence=0.9, output={"parsed_structure": {"dashboards": [{"name": "d1"}], "visuals": [{}]}})


class _Phase2Tool(_Tool):
    def __init__(self) -> None:
        super().__init__("semantic_reasoning")

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={
                "semantic_graph": {
                    "columns": [{"name": "Country", "role": "dimension"}, {"name": "SalesAmount", "role": "measure"}],
                    "measures": [{"name": "Sales", "role": "measure", "expression": "SUM(SalesAmount)"}],
                    "confidence_score": 0.9,
                }
            },
        )


class _Phase3Tool(_Tool):
    def __init__(self) -> None:
        super().__init__("specification")

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={
                "abstract_spec": {
                    "dashboard_spec": {
                        "pages": [
                            {
                                "visuals": [
                                    {
                                        "id": "v1",
                                        "type": "columnchart",
                                        "data_binding": {"axes": {"x": "Country", "y": "SalesAmount"}},
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
        )


class _Phase4Tool(_Tool):
    def __init__(self) -> None:
        super().__init__("transformation")

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={
                "tool_model": {
                    "datasets": [{"name": "sales_data", "fields": [{"name": "Country"}, {"name": "SalesAmount"}]}],
                    "visuals": [{"dataset": "sales_data", "tool_visual_type": "columnchart"}],
                    "validation_results": [],
                }
            },
        )


class _Phase5Tool(_Tool):
    def __init__(self) -> None:
        super().__init__("export")

    def execute(self, state: dict):
        self.calls += 1
        return PhaseAgentResult(
            status="success",
            confidence=0.9,
            output={"export_result": {"validation": {"is_valid": True, "errors": [], "warnings": []}, "content_bytes": 256}},
        )


class _SelfEvalSequencer:
    def __init__(self) -> None:
        self.p3_calls = 0
        self.p5_calls = 0

    def evaluate_phase3(self, output: dict) -> SelfEvalResult:
        self.p3_calls += 1
        if self.p3_calls == 1:
            return SelfEvalResult(score=0.5, issues=["phase3 low"], provider="mock")
        return SelfEvalResult(score=0.92, issues=[], provider="mock")

    def evaluate_phase5(self, output: dict) -> SelfEvalResult:
        self.p5_calls += 1
        if self.p5_calls == 1:
            return SelfEvalResult(score=0.6, issues=["phase5 low"], provider="mock")
        return SelfEvalResult(score=0.93, issues=[], provider="mock")

    def is_below_threshold(self, phase_name: str, result: SelfEvalResult) -> bool:
        if phase_name == "specification":
            return result.score < 0.7
        if phase_name == "export":
            return result.score < 0.75
        return False


@pytest.mark.integration
def test_agentic_loop_end_to_end_with_retries_self_eval_and_fixes(tmp_path: Path) -> None:
    trace = tmp_path / "agentic_trace.jsonl"
    snapshots = tmp_path / "snapshots"

    p0 = _Phase0Tool()
    p1 = _Phase1Tool()
    p2 = _Phase2Tool()
    p3 = _Phase3Tool()
    p4 = _Phase4Tool()
    p5 = _Phase5Tool()

    orchestrator = AgentOrchestrator(
        max_retries=2,
        trace_file=trace,
        debug_snapshot_dir=snapshots,
        enable_llm_fallback=False,
        enable_llm_self_eval=True,
        enable_phase_cache=False,
    )
    for tool in (p0, p1, p2, p3, p4, p5):
        orchestrator.register_tool(tool)

    orchestrator._self_evaluator = _SelfEvalSequencer()

    state = AgentState(
        execution_id="it-loop-001",
        artifacts={"source_path": "demo.twbx", "output_path": "demo.rdl"},
        context={"intent": {"type": "conversion"}},
    )

    result = orchestrator.run_conversion_flow(state)

    assert result["export"].status == "success"
    # parsing retried due to gate + specification/export retried due to self-eval low first score
    assert p1.calls == 2
    assert p3.calls == 2
    assert p5.calls == 2
    assert trace.exists()
    assert any(snapshots.glob("*.json"))
    assert len(state.react_history) >= 6


@pytest.mark.integration
def test_agentic_loop_cache_hit_skips_all_phase_reruns(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"

    p0 = _Phase0Tool()
    p1 = _Phase1Tool()
    p2 = _Phase2Tool()
    p3 = _Phase3Tool()
    p4 = _Phase4Tool()
    p5 = _Phase5Tool()

    orchestrator1 = AgentOrchestrator(
        max_retries=1,
        trace_file=tmp_path / "trace_1.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_1",
        enable_llm_fallback=False,
        enable_llm_self_eval=False,
        enable_phase_cache=True,
        cache_dir=cache_dir,
    )
    for tool in (p0, p1, p2, p3, p4, p5):
        orchestrator1.register_tool(tool)

    state1 = AgentState(
        execution_id="it-cache-001",
        artifacts={"source_path": "demo.twbx", "output_path": "demo.rdl"},
        context={"intent": {"type": "conversion"}},
    )
    orchestrator1.run_conversion_flow(state1)

    initial_counts = {tool.name: tool.calls for tool in (p0, p1, p2, p3, p4, p5)}

    orchestrator2 = AgentOrchestrator(
        max_retries=1,
        trace_file=tmp_path / "trace_2.jsonl",
        debug_snapshot_dir=tmp_path / "snapshots_2",
        enable_llm_fallback=False,
        enable_llm_self_eval=False,
        enable_phase_cache=True,
        cache_dir=cache_dir,
    )
    # Reuse same tool instances to assert no additional execute() is called on second run.
    for tool in (p0, p1, p2, p3, p4, p5):
        orchestrator2.register_tool(tool)

    state2 = AgentState(
        execution_id="it-cache-002",
        artifacts={"source_path": "demo.twbx", "output_path": "demo.rdl"},
        context={"intent": {"type": "conversion"}},
    )
    result2 = orchestrator2.run_conversion_flow(state2)

    assert result2["export"].status == "success"
    assert {tool.name: tool.calls for tool in (p0, p1, p2, p3, p4, p5)} == initial_counts

    cached_artifacts = state2.context.get("cached_artifacts") or {}
    assert "data_extraction" in cached_artifacts
    assert "parsing" in cached_artifacts
    assert "specification" in cached_artifacts
