import os

import pytest

from viz_agent.phase2_semantic.graph import SemanticGraph


@pytest.mark.integration
def test_semantic_graph_local_neo4j_roundtrip():
    if os.getenv("VIZ_AGENT_SEMANTIC_GRAPH_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Neo4j integration disabled")

    graph = SemanticGraph.from_env()
    if graph is None:
        pytest.skip("Neo4j not configured (missing credentials)")

    try:
        assert graph.ping() is True
        nodes = [
            {"id": "it:table:sales_data", "label": "Table", "name": "sales_data"},
            {"id": "it:term:Revenue", "label": "BusinessTerm", "name": "Revenue"},
        ]
        rels = [{"source_id": "it:table:sales_data", "target_id": "it:term:Revenue", "type": "MAPPED_TO"}]
        graph.upsert_payload(nodes, rels)

        records = graph.query_graph("MATCH (n:Generic {id: 'it:table:sales_data'}) RETURN n.id AS id")
        assert records and records[0]["id"] == "it:table:sales_data"
    finally:
        graph.close()
