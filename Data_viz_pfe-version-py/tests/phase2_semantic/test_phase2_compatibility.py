import pandas as pd

from viz_agent.models.abstract_spec import DataSource, ParsedWorkbook
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry, ResolvedDataSource
from viz_agent.phase2_semantic.phase2_orchestrator import Phase2SemanticOrchestrator
from viz_agent.phase3_spec.abstract_spec_builder import AbstractSpecBuilder


class _FakeMistralClient:
    def chat_json(self, system_prompt: str, user_prompt: str):
        return {
            "column_labels": {},
            "suggested_measures": [
                {"name": "Sum Total Sales", "expression": "SUM([Sales Amount])", "source": "calc_sales"}
            ],
            "hierarchies": [],
            "column_roles": {},
        }


def test_phase2_output_compatible_with_phase3_builder():
    registry = DataSourceRegistry()
    frame = pd.DataFrame(
        {
            "CustomerKey": [1, 2],
            "ProductKey": [10, 11],
            "Sales Amount": [100.0, 250.0],
        }
    )
    registry.register("sales", ResolvedDataSource(name="sales", source_type="hyper", frames={"sales_data": frame}))

    workbook = ParsedWorkbook(
        datasources=[DataSource(name="sales_data", caption="Sales")],
        dashboards=[],
        worksheets=[],
        calculated_fields=[],
        data_registry=registry,
    )

    semantic_model, lineage, artifacts = Phase2SemanticOrchestrator(llm_client=_FakeMistralClient()).run(workbook)
    spec = AbstractSpecBuilder.build(workbook, {"action": "export_rdl"}, semantic_model, lineage)

    assert spec.semantic_model.fact_table == "sales_data"
    assert isinstance(artifacts.get("mappings", []), list)
    assert "graph" in artifacts
