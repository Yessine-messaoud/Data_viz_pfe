from __future__ import annotations

import pandas as pd

from viz_agent.models.abstract_spec import (
    ColumnDef,
    ColumnRef,
    DataLineageSpec,
    DataSource,
    JoinDef,
    Measure,
    ParsedWorkbook,
    SemanticModel,
    TableRef,
    Worksheet,
)
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry, ResolvedDataSource
from viz_agent.phase2_semantic.fact_table_detector import detect_fact_table, filter_fk_measures
from viz_agent.phase2_semantic.graph import SemanticGraph
from viz_agent.phase2_semantic.hybrid_semantic_layer import HybridSemanticLayer
from viz_agent.phase2_semantic.join_resolver import JoinResolver
from viz_agent.phase2_semantic.schema_mapper import TableauSchemaMapper


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
        worksheets=[
            Worksheet(
                name="SO_Sales",
                mark_type="Bar",
                datasource_name="sales_data",
                rows_shelf=[ColumnRef(table="sales_data", column="Sales Amount")],
                cols_shelf=[ColumnRef(table="sales_data", column="CustomerKey")],
            )
        ],
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


def test_hybrid_semantic_layer_fallback_when_llm_returns_no_measures() -> None:
    registry = DataSourceRegistry()
    frame = pd.DataFrame(
        {
            "CustomerKey": [1, 2],
            "SalesAmount": [100.0, 250.0],
            "TaxAmt": [10.0, 25.0],
        }
    )
    registry.register("sales", ResolvedDataSource(name="sales", source_type="hyper", frames={"sales_data": frame}))

    workbook = ParsedWorkbook(
        datasources=[DataSource(name="sales_data", caption="Sales")],
        dashboards=[],
        worksheets=[
            Worksheet(
                name="SO_Sales",
                mark_type="Bar",
                datasource_name="sales_data",
                rows_shelf=[ColumnRef(table="sales_data", column="SalesAmount")],
                cols_shelf=[ColumnRef(table="sales_data", column="CustomerKey")],
            )
        ],
        calculated_fields=[],
        data_registry=registry,
    )

    class FakeEmptyClient:
        def chat_json(self, system_prompt: str, user_prompt: str):
            return {
                "column_labels": {},
                "suggested_measures": [],
                "hierarchies": [],
                "column_roles": {},
            }

    semantic_model, _lineage = HybridSemanticLayer(llm_client=FakeEmptyClient()).enrich(workbook)
    measure_names = [m.name for m in semantic_model.measures]
    assert any(name.startswith("Sum ") for name in measure_names)


def test_schema_mapper_deduplicates_tables_by_name() -> None:
    workbook = ParsedWorkbook(
        datasources=[
            DataSource(
                name="federated.x1",
                caption="Extract",
                columns=[ColumnDef(name="Country"), ColumnDef(name="SalesAmount", role="measure")],
            ),
            DataSource(
                name="federated.x1",
                caption="Extract",
                columns=[ColumnDef(name="Country"), ColumnDef(name="OrderQuantity", role="measure")],
            ),
        ],
        dashboards=[],
        worksheets=[],
        calculated_fields=[],
        data_registry=DataSourceRegistry(),
    )

    schema_map = TableauSchemaMapper().map(workbook)
    assert len(schema_map.tables) == 1
    assert schema_map.tables[0].name == "Extract"
    assert schema_map.tables[0].source_name == "federated.x1"
    assert schema_map.physical_to_logical.get("federated.x1") == "Extract"
    col_names = [c.name for c in schema_map.tables[0].columns]
    assert col_names.count("Country") == 1
    assert "SalesAmount" in col_names
    assert "OrderQuantity" in col_names


def test_join_resolver_prefers_tableau_relationships_over_heuristic_id() -> None:
    datasources = [DataSource(name="federated.a"), DataSource(name="federated.b")]
    relationships = [
        {
            "left_table": "federated.a",
            "right_table": "federated.b",
            "left_col": "CustomerKey",
            "right_col": "CustomerKey",
            "type": "LEFT",
            "source_xml_ref": "[federated.a].[CustomerKey] = [federated.b].[CustomerKey]",
        }
    ]

    joins = JoinResolver().resolve(
        datasources,
        tableau_relationships=relationships,
        table_name_map={"federated.a": "sales_data", "federated.b": "customer_data"},
    )

    assert len(joins) == 1
    assert joins[0].left_table == "sales_data"
    assert joins[0].right_table == "customer_data"
    assert joins[0].left_col == "CustomerKey"
    assert joins[0].right_col == "CustomerKey"
    assert joins[0].type == "LEFT"
    assert joins[0].source_xml_ref != ""


def test_join_resolver_infers_real_join_from_columns_without_relationships() -> None:
    datasources = [
        DataSource(
            name="sales",
            columns=[
                ColumnDef(name="SalesOrderNumber"),
                ColumnDef(name="CustomerKey"),
                ColumnDef(name="Amount"),
            ],
        ),
        DataSource(
            name="customer",
            columns=[
                ColumnDef(name="CustomerKey"),
                ColumnDef(name="CustomerName"),
            ],
        ),
    ]

    joins = JoinResolver().resolve(datasources)

    assert len(joins) == 1
    assert joins[0].left_col == "CustomerKey"
    assert joins[0].right_col == "CustomerKey"
    assert joins[0].source_xml_ref == "inferred_from_columns"


def test_semantic_graph_payload_is_deterministic_and_deduplicated() -> None:
    semantic_model = SemanticModel(
        entities=[
            TableRef(
                id="t1",
                name="sales_data",
                columns=[
                    ColumnDef(name="Country", role="dimension", pbi_type="text"),
                    ColumnDef(name="SalesAmount", role="measure", pbi_type="decimal"),
                ],
            )
        ],
        measures=[Measure(name="SalesAmount", expression="SUM([SalesAmount])")],
        fact_table="sales_data",
    )
    lineage = DataLineageSpec(
        tables=[
            TableRef(
                id="t1",
                name="sales_data",
                columns=[
                    ColumnDef(name="Country", role="dimension", pbi_type="text"),
                    ColumnDef(name="SalesAmount", role="measure", pbi_type="decimal"),
                ],
            )
        ],
        joins=[],
    )

    payload1 = SemanticGraph.build_payload(
        semantic_model,
        lineage,
        mappings=[
            {"column": "Country", "mapped_business_term": "Country", "confidence": 0.9, "method": "rule"},
            {"column": "Country", "mapped_business_term": "Country", "confidence": 0.9, "method": "rule"},
        ],
        ontology_terms=["Country", "Country"],
    )
    payload2 = SemanticGraph.build_payload(
        semantic_model,
        lineage,
        mappings=[
            {"column": "Country", "mapped_business_term": "Country", "confidence": 0.9, "method": "rule"},
        ],
        ontology_terms=["Country"],
    )

    node_ids_1 = [node["id"] for node in payload1["nodes"]]
    rel_ids_1 = [f"{rel['source_id']}|{rel['type']}|{rel['target_id']}" for rel in payload1["relationships"]]
    assert len(node_ids_1) == len(set(node_ids_1))
    assert len(rel_ids_1) == len(set(rel_ids_1))

    assert {node["id"] for node in payload1["nodes"]} == {node["id"] for node in payload2["nodes"]}
    assert {
        f"{rel['source_id']}|{rel['type']}|{rel['target_id']}" for rel in payload1["relationships"]
    } == {
        f"{rel['source_id']}|{rel['type']}|{rel['target_id']}" for rel in payload2["relationships"]
    }
