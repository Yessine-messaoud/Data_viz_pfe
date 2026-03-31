from viz_agent.models.abstract_spec import ColumnDef, DataLineageSpec, JoinDef, Measure, SemanticModel, TableRef
from viz_agent.phase2_semantic.graph import SemanticGraph


def test_build_payload_models_nodes_and_relationships():
    semantic_model = SemanticModel(
        entities=[],
        measures=[Measure(name="Total Sales", expression="SUM([Sales Amount])")],
        dimensions=[],
        hierarchies=[],
        relationships=[],
        glossary=[],
        fact_table="sales_data",
        grain="row",
    )
    lineage = DataLineageSpec(
        tables=[
            TableRef(
                id="t_sales",
                name="sales_data",
                columns=[
                    ColumnDef(name="CustomerKey", role="dimension"),
                    ColumnDef(name="Sales Amount", role="measure"),
                ],
            ),
            TableRef(
                id="t_customer",
                name="customer_data",
                columns=[ColumnDef(name="CustomerKey", role="dimension")],
            ),
        ],
        joins=[
            JoinDef(
                id="j1",
                left_table="sales_data",
                right_table="customer_data",
                left_col="CustomerKey",
                right_col="CustomerKey",
            )
        ],
    )
    mappings = [
        {
            "column": "Sales Amount",
            "mapped_business_term": "Revenue",
            "confidence": 0.91,
            "method": "heuristic",
        }
    ]

    payload = SemanticGraph.build_payload(semantic_model, lineage, mappings=mappings, ontology_terms=["Revenue"])

    assert payload["nodes"]
    assert payload["relationships"]
    labels = {node["label"] for node in payload["nodes"]}
    rel_types = {rel["type"] for rel in payload["relationships"]}

    assert "Table" in labels
    assert "Column" in labels
    assert "Measure" in labels
    assert "BusinessTerm" in labels
    assert "HAS_COLUMN" in rel_types
    assert "JOINS_TO" in rel_types
    assert "MAPPED_TO" in rel_types


def test_graph_from_env_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VIZ_AGENT_SEMANTIC_GRAPH_ENABLED", raising=False)
    assert SemanticGraph.from_env() is None
