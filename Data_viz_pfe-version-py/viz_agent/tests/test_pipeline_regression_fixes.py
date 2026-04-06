from __future__ import annotations

from unittest.mock import MagicMock

from viz_agent.models.abstract_spec import (
    AbstractSpec,
    ColumnDef,
    ColumnRef,
    DashboardPage,
    DashboardSpec,
    DataBinding,
    DataLineageSpec,
    DataSource,
    Filter,
    JoinDef,
    Measure,
    SemanticModel,
    TableRef,
    VisualSpec,
)
from viz_agent.phase2_semantic.join_resolver import JoinResolver
from viz_agent.phase4_transform.transformation_agent import TransformationAgent
from viz_agent.phase4_transform.rdl_dataset_mapper import RDLDataset, RDLField
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
from viz_agent.phase5_rdl.rdl_layout_builder import RDLLayoutBuilder


def test_regression_join_resolver_prefers_real_key_match() -> None:
    datasources = [
        DataSource(name="sales", columns=[ColumnDef(name="CustomerKey"), ColumnDef(name="SalesAmount")]),
        DataSource(name="customer", columns=[ColumnDef(name="CustomerKey"), ColumnDef(name="CustomerName")]),
    ]

    joins = JoinResolver().resolve(datasources)

    assert joins
    assert joins[0].left_col == "CustomerKey"
    assert joins[0].right_col == "CustomerKey"
    assert joins[0].source_xml_ref == "inferred_from_columns"


def test_regression_filter_invalid_dimension_aggregated_measure() -> None:
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
            Measure(name="BadCountrySum", expression="SUM(Country)"),
            Measure(name="GoodSalesSum", expression="SUM(SalesAmount)"),
        ],
    )

    translated = agent._translate_measures(semantic_model)
    names = [m["name"] for m in translated]

    assert "BadCountrySum" not in names
    assert "GoodSalesSum" in names


def test_regression_visual_type_and_size_binding_sanitization() -> None:
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
        ]
    )
    visual = {
        "id": "v1",
        "type": "chart",
        "rdl_type": "chart",
        "tool_visual_type": "chart",
        "data_binding": {"axes": {"x": "Country", "y": "SalesAmount", "size": "Country"}},
    }

    fixed = agent._normalize_visual_type(dict(visual))
    fixed = agent._sanitize_size_binding(fixed, semantic_model)

    assert fixed["tool_visual_type"] == "columnchart"
    assert fixed["rdl_type"] == "columnchart"
    assert fixed["type"] == "columnchart"
    assert "size" not in ((fixed.get("data_binding") or {}).get("axes") or {})


def test_regression_rdl_propagates_filters_and_datasource_metadata() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT Country, SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )
    visual = VisualSpec(
        id="v1",
        source_worksheet="ws1",
        type="chart",
        title="Sales",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="sales_data", column="Country"),
                "y": ColumnRef(table="sales_data", column="SalesAmount"),
            }
        ),
    )
    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(
            pages=[DashboardPage(id="p1", name="Sales", visuals=[visual])],
            global_filters=[Filter(field="Country", operator="=", value="France")],
        ),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[
                TableRef(
                    id="t1",
                    name="sales_data",
                    columns=[ColumnDef(name="Country"), ColumnDef(name="SalesAmount")],
                )
            ],
            joins=[JoinDef(id="j1", left_table="sales_data", right_table="sales_data", left_col="Country", right_col="Country")],
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert "Datasources:" in xml
    assert "<rd:DataSourceID>" in xml
    assert "<Filters>" in xml
    assert "<FilterExpression>=Fields!Country.Value</FilterExpression>" in xml
    assert "=Parameters!Country.Value" in xml
