from __future__ import annotations

from viz_agent.phase4_transform.agent.compatibility_manager import CompatibilityManager
from viz_agent.phase4_transform.agent.transformation_agent import TransformationAgent
from viz_agent.phase4_transform.agent.validation_hook import ValidationHook


def _abstract_spec_payload() -> dict:
    return {
        "id": "spec-1",
        "version": "2.0.0",
        "semantic_model": {
            "fact_table": "sales",
            "entities": [
                {
                    "name": "sales",
                    "columns": [
                        {"name": "Country", "pbi_type": "STRING", "role": "dimension"},
                        {"name": "SalesAmount", "pbi_type": "DECIMAL", "role": "measure"},
                    ],
                }
            ],
            "measures": [{"name": "Total Sales", "expression": "SUM(SalesAmount)"}],
        },
        "dashboard_spec": {
            "global_filters": [],
            "pages": [
                {
                    "id": "p1",
                    "name": "Main",
                    "visuals": [
                        {
                            "id": "v1",
                            "title": "Sales by Country",
                            "type": "bar",
                            "rdl_type": "chart",
                            "data_binding": {
                                "axes": {
                                    "x": {"table": "sales", "column": "Country"},
                                    "y": {"table": "sales", "column": "SalesAmount"},
                                }
                            },
                        }
                    ],
                }
            ],
        },
    }


def test_transformation_agent_generates_tool_model_for_rdl() -> None:
    payload = _abstract_spec_payload()
    model = TransformationAgent().transform(payload, "RDL", context={}, intent=None)
    assert "error" not in model
    assert isinstance(model.get("datasets"), list) and model["datasets"]
    assert isinstance(model.get("visuals"), list) and model["visuals"]
    assert model["visuals"][0].get("tool_visual_type") == "ColumnChart"


def test_compatibility_manager_fallback_for_looker() -> None:
    tool_model = {
        "visuals": [{"id": "v1", "business_type": "treemap", "tool_visual_type": "treemap"}],
    }
    updated, logs = CompatibilityManager().resolve(tool_model, "LOOKER", {})
    assert updated["visuals"][0]["business_type"] == "bar"
    assert logs


def test_phase4_validation_rejects_generic_chart_type() -> None:
    issues = ValidationHook().validate({"datasets": [], "visuals": [{"business_type": "chart"}]})
    codes = [issue.get("code") for issue in issues]
    assert "P4_V006" in codes

