from __future__ import annotations

from viz_agent.models.abstract_spec import ColumnDef, Measure, SemanticModel, TableRef
from viz_agent.phase4_transform.transformation_agent import TransformationAgent
from viz_agent.orchestrator.phase_tool_agents import (
    Phase0ToolAgent,
    Phase1ToolAgent,
    Phase2ToolAgent,
    Phase3ToolAgent,
    Phase4ToolAgent,
    Phase5ToolAgent,
)


def test_phase0_tool_result_contract() -> None:
    agent = Phase0ToolAgent()

    class _Fake:
        def run(self, step):
            return {"validation_status": "passed", "data": {"tables": [{"name": "t1"}]}}

    agent._agent = _Fake()
    result = agent.execute({"artifacts": {"source_path": "demo.twbx"}})

    assert result.status in {"success", "low_confidence", "error"}
    assert isinstance(result.confidence, float)
    assert "metadata" in result.output


def test_phase1_tool_result_contract() -> None:
    agent = Phase1ToolAgent()

    class _Fake:
        def parse(self, artifact_path, metadata, context):
            return {"dashboards": [{"name": "d1"}], "visuals": [{"id": "v1"}]}

    agent._agent = _Fake()
    result = agent.execute({"artifacts": {"source_path": "demo.twbx"}, "previous_outputs": {"data_extraction": {"metadata": {}}}})

    assert result.status == "success"
    assert "parsed_structure" in result.output


def test_phase2_to_phase5_tools_result_contracts() -> None:
    phase2 = Phase2ToolAgent()
    phase3 = Phase3ToolAgent()
    phase4 = Phase4ToolAgent()
    phase5 = Phase5ToolAgent()

    class _SemFake:
        def build_semantic_graph(self, metadata, parsed_structure, intent=None):
            return {"nodes": [1], "confidence_score": 0.9}

    class _SpecFake:
        def generate_specification(self, semantic_graph, intent, context):
            return {"confidence_score": 0.9, "spec": {"ok": True}}

    class _TransformFake:
        def transform(self, abstract_spec, target_tool, context, intent=None):
            return {"datasets": [{"name": "ds"}], "visuals": [{"dataset": "ds", "tool_visual_type": "tablix"}], "validation_results": []}

    class _ExportFake:
        def export(self, model, target_format):
            return {"format": "rdl", "content": b"<Report/>", "metadata": {"filename": "x.rdl"}, "validation": {"is_valid": True}}

    phase2._agent = _SemFake()
    phase3._agent = _SpecFake()
    phase4._agent = _TransformFake()
    phase5._agent = _ExportFake()

    state = {
        "context": {"intent": {"type": "conversion"}},
        "previous_outputs": {
            "data_extraction": {"metadata": {}},
            "parsing": {"parsed_structure": {"dashboards": [1], "visuals": [1]}},
            "semantic_reasoning": {"semantic_graph": {"nodes": [1]}},
            "specification": {"abstract_spec": {"semantic_model": {}, "data_lineage": {}, "dashboard_spec": {"pages": []}}},
            "transformation": {"tool_model": {"ok": True}},
        },
    }

    r2 = phase2.execute(state)
    assert r2.status == "success"

    state["previous_outputs"]["semantic_reasoning"] = r2.output
    r3 = phase3.execute(state)
    assert r3.status == "success"

    state["previous_outputs"]["specification"] = r3.output
    r4 = phase4.execute(state)
    assert r4.status in {"success", "low_confidence"}

    state["previous_outputs"]["transformation"] = r4.output
    r5 = phase5.execute(state)
    assert r5.status in {"success", "low_confidence"}
    assert "export_result" in r5.output


def test_transformation_agent_removes_invalid_dimension_aggregations() -> None:
    agent = TransformationAgent()
    semantic_model = SemanticModel(
        entities=[
            TableRef(
                id="t1",
                name="sales",
                columns=[
                    ColumnDef(name="Country", role="dimension"),
                    ColumnDef(name="SalesAmount", role="measure"),
                ],
            )
        ],
        measures=[
            Measure(name="Bad", expression="SUM(Country)"),
            Measure(name="Good", expression="SUM(SalesAmount)"),
        ],
    )

    measures = agent._translate_measures(semantic_model)
    names = [m.get("name") for m in measures]
    assert "Bad" not in names
    assert "Good" in names


def test_transformation_agent_normalizes_chart_type_and_cleans_size_dimension() -> None:
    agent = TransformationAgent()
    semantic_model = SemanticModel(
        entities=[
            TableRef(
                id="t1",
                name="sales",
                columns=[
                    ColumnDef(name="Country", role="dimension"),
                    ColumnDef(name="SalesAmount", role="measure"),
                ],
            )
        ],
    )
    visual = {
        "id": "v1",
        "type": "chart",
        "rdl_type": "chart",
        "tool_visual_type": "chart",
        "data_binding": {"axes": {"x": "Country", "size": "Country", "y": "SalesAmount"}},
    }

    normalized = agent._normalize_visual_type(dict(visual))
    sanitized = agent._sanitize_size_binding(normalized, semantic_model)

    assert sanitized.get("type") == "columnchart"
    axes = (sanitized.get("data_binding") or {}).get("axes") or {}
    assert "size" not in axes
