from __future__ import annotations

from viz_agent.orchestrator.modular_agents import ParsingAgent, SemanticAgent, VisualizationAgent
from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.pipeline_context import PipelineContext


class _FakeTool:
    def __init__(self, phase_name: str):
        self.phase_name = phase_name
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        if self.phase_name == "parsing":
            return PhaseAgentResult(status="success", confidence=0.92, output={"parsed_structure": {"worksheets": [{"name": "ws1"}]}})
        if self.phase_name == "semantic_reasoning":
            return PhaseAgentResult(status="success", confidence=0.9, output={"semantic_graph": {"measures": [{"name": "Sales"}]}})
        return PhaseAgentResult(status="success", confidence=0.88, output={"abstract_spec": {"dashboard_spec": {"pages": []}}})


def test_pipeline_context_model_and_wrappers_update_context() -> None:
    ctx = PipelineContext(
        runtime_context={"intent": {"type": "conversion"}},
        artifacts={"source_path": "demo.twbx"},
        previous_outputs={
            "data_extraction": {"metadata": {"tables": [{"name": "sales"}]}}
        },
    )

    parsing = ParsingAgent(tool=_FakeTool("parsing"))
    semantic = SemanticAgent(tool=_FakeTool("semantic_reasoning"))
    viz = VisualizationAgent(tool=_FakeTool("specification"))

    r1 = parsing.execute(ctx)
    assert r1.status == "success"
    assert "parsing" in ctx.previous_outputs

    r2 = semantic.execute(ctx)
    assert r2.status == "success"
    assert ctx.semantic_model.get("measures")

    r3 = viz.execute(ctx)
    assert r3.status == "success"
    assert "dashboard_spec" in ctx.abstract_spec

    assert ctx.confidence_scores["parsing"] > 0.8
    assert ctx.confidence_scores["semantic_reasoning"] > 0.8
    assert ctx.confidence_scores["specification"] > 0.8
