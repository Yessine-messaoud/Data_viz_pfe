from __future__ import annotations

import pandas as pd

from viz_agent.models.abstract_spec import (
    ColumnDef,
    DataSource,
    JoinDef,
    Measure,
    ParsedWorkbook,
    TableRef,
)
from viz_agent.phase0_data.data_source_registry import DataSourceRegistry, ResolvedDataSource
from viz_agent.phase2_semantic.fact_table_detector import detect_fact_table, filter_fk_measures
from viz_agent.phase2_semantic.hybrid_semantic_layer import HybridSemanticLayer


def test_detect_fact_table_adventureworks() -> None:
    tables = [
        TableRef(
            id="t1",
            name="sales_data",
            columns=[
                ColumnDef(name="CustomerKey"),
                ColumnDef(name="ProductKey"),
                ColumnDef(name="DateKey"),
                ColumnDef(name="Sales Amount"),
            ],
        ),
        TableRef(
            id="t2",
            name="customer_data",
            columns=[
                ColumnDef(name="Customer"),
                ColumnDef(name="Customer ID"),
            ],
        ),
    ]
    joins = [
        JoinDef(
            id="j1",
            left_table="sales_data",
            right_table="customer_data",
            left_col="CustomerKey",
            right_col="CustomerKey",
        )
    ]

    assert detect_fact_table(tables, joins) == "sales_data"


def test_filter_fk_measures() -> None:
    measures = [
        Measure(name="Sum Total Sales", expression="SUM([Sales Amount])"),
        Measure(name="Sum Customer Key", expression="SUM([Customer Key])"),
        Measure(name="Sum Profit", expression="SUM([Profit])"),
        Measure(name="Sum Date Key", expression="SUM([Date Key])"),
    ]

    result = filter_fk_measures(measures)
    names = [m.name for m in result]

    assert "Sum Total Sales" in names
    assert "Sum Profit" in names
    assert "Sum Customer Key" not in names
    assert "Sum Date Key" not in names
    assert len(result) == 2


def test_hybrid_semantic_layer_returns_semantic_and_lineage() -> None:
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

    class FakeMistralClient:
        def chat_json(self, system_prompt: str, user_prompt: str):
            return {
                "column_labels": {},
                "suggested_measures": [
                    {"name": "Sum Total Sales", "expression": "SUM([Sales Amount])", "source": "calc_sales"}
                ],
                "hierarchies": [],
            }

    semantic_model, lineage = HybridSemanticLayer(llm_client=FakeMistralClient()).enrich(workbook)

    assert semantic_model.fact_table == "sales_data"
    assert len(lineage.tables) == 1
    assert lineage.tables[0].name == "sales_data"
