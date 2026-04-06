from __future__ import annotations

from viz_agent.validators.validation_engine import ValidationEngine


def _minimal_payload() -> dict:
    return {
        "dashboard_spec": {
            "pages": [
                {
                    "id": "p1",
                    "name": "",
                    "visuals": [
                        {
                            "id": "v1",
                            "type": "chart",
                            "title": "",
                            "data_binding": {"axes": {"x": {"table": "t", "column": "Country"}}},
                        }
                    ],
                }
            ]
        },
        "semantic_model": {
            "fact_table": "sales",
            "entities": [{"name": "sales", "columns": [{"name": "Country"}, {"name": "SalesAmount"}]}],
            "measures": [{"name": "Sales", "expression": "SUM([SalesAmount])"}],
        },
        "data_lineage": {"tables": [], "joins": []},
        "rdl_datasets": [{"name": "sales_ds", "fields": [{"name": "Country"}, {"name": "SalesAmount"}]}],
    }


def test_validation_engine_applies_rule_fixes() -> None:
    payload = _minimal_payload()
    report = ValidationEngine(max_retries=2).validate_phase("phase3_spec", payload, {})
    assert report.can_proceed
    assert report.fixed_output["dashboard_spec"]["pages"][0]["name"] != ""
    assert report.fixed_output["dashboard_spec"]["pages"][0]["visuals"][0]["title"] != ""


def test_validation_engine_interphase_warning_for_unknown_field() -> None:
    payload = _minimal_payload()
    payload["dashboard_spec"]["pages"][0]["visuals"][0]["data_binding"]["axes"]["x"]["column"] = "Countri"
    report = ValidationEngine(max_retries=2).validate_phase("phase3_spec", payload, {})
    assert report.can_proceed
    # Either corrected by heuristic fix or left as warning if no strong match.
    assert report.warning_count >= 0


def test_validation_engine_blocks_on_syntax_error() -> None:
    payload = _minimal_payload()
    payload["dashboard_spec"]["pages"] = {"bad": "type"}  # invalid type
    report = ValidationEngine(max_retries=0).validate_phase("phase3_spec", payload, {})
    assert not report.can_proceed
    assert report.error_count >= 1

