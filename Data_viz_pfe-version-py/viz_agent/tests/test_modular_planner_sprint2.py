from __future__ import annotations

from viz_agent.orchestrator.modular_planner import PlannerAgent
from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.pipeline_context import PipelineContext


def _valid_abstract_spec_output() -> dict:
    return {
        "abstract_spec": {
            "dashboard_spec": {
                "pages": [
                    {
                        "visuals": [
                            {
                                "type": "columnchart",
                                "data_binding": {
                                    "axes": {
                                        "x": "Category",
                                        "y": "Sales",
                                    }
                                },
                            }
                        ]
                    }
                ]
            }
        }
    }


class _FakeAgent:
    def __init__(self, name: str, result_sequence: list[PhaseAgentResult]):
        self.name = name
        self._seq = list(result_sequence)
        self.calls = 0

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        idx = min(self.calls, len(self._seq) - 1)
        self.calls += 1
        result = self._seq[idx].normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        return result


def test_planner_retries_low_confidence_and_succeeds() -> None:
    parsing = _FakeAgent(
        "parsing",
        [
            PhaseAgentResult(status="low_confidence", confidence=0.6, output={"parsed_structure": {}}),
            PhaseAgentResult(
                status="success",
                confidence=0.9,
                output={"parsed_structure": {"worksheets": [{"name": "ws1"}]}}
            ),
        ],
    )
    semantic = _FakeAgent(
        "semantic_reasoning",
        [PhaseAgentResult(status="success", confidence=0.91, output={"semantic_graph": {"columns": []}})],
    )
    spec = _FakeAgent(
        "specification",
        [
            PhaseAgentResult(
                status="success",
                confidence=0.9,
                output=_valid_abstract_spec_output(),
            )
        ],
    )
    transform = _FakeAgent(
        "transformation",
        [PhaseAgentResult(status="success", confidence=0.87, output={"tool_model": {"datasets": []}})],
    )
    export = _FakeAgent(
        "export",
        [
            PhaseAgentResult(
                status="success",
                confidence=0.93,
                output={"export_result": {"validation": {"is_valid": True}, "content_bytes": 120}},
            )
        ],
    )

    planner = PlannerAgent(agents=[parsing, semantic, spec, transform, export], max_retries=2, enable_phase_cache=False)
    ctx = PipelineContext(runtime_context={"intent": {"type": "conversion"}}, artifacts={"source_path": "demo.twbx"})

    result = planner.run(ctx)

    assert result.status == "success"
    assert parsing.calls == 2
    assert result.retries["parsing"] == 1
    assert result.phase_results["validation"].status == "success"


def test_planner_fails_when_export_gate_invalid() -> None:
    parsing = _FakeAgent(
        "parsing",
        [
            PhaseAgentResult(
                status="success",
                confidence=0.9,
                output={"parsed_structure": {"worksheets": [{"name": "ws1"}]}}
            )
        ],
    )
    semantic = _FakeAgent(
        "semantic_reasoning",
        [PhaseAgentResult(status="success", confidence=0.91, output={"semantic_graph": {"columns": []}})],
    )
    spec = _FakeAgent(
        "specification",
        [
            PhaseAgentResult(
                status="success",
                confidence=0.9,
                output=_valid_abstract_spec_output(),
            )
        ],
    )
    transform = _FakeAgent(
        "transformation",
        [PhaseAgentResult(status="success", confidence=0.87, output={"tool_model": {"datasets": []}})],
    )
    export = _FakeAgent(
        "export",
        [
            PhaseAgentResult(
                status="success",
                confidence=0.9,
                output={"export_result": {"validation": {"is_valid": False}, "content_bytes": 0}},
            )
        ],
    )

    planner = PlannerAgent(agents=[parsing, semantic, spec, transform, export], max_retries=0, enable_phase_cache=False)
    ctx = PipelineContext(runtime_context={"intent": {"type": "conversion"}}, artifacts={"source_path": "demo.twbx"})

    result = planner.run(ctx)

    assert result.status == "failed"
    assert result.phase_results["export"].status == "success"
    assert result.phase_results["validation"].status == "error"
    assert any("Phase5 gate failed" in err for err in result.errors)
