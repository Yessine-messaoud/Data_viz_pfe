from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class SemanticGraph:
    @classmethod
    def from_env(cls) -> "SemanticGraph | None":
        enabled = os.getenv("VIZ_AGENT_SEMANTIC_GRAPH_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not enabled:
            return None

        uri = os.getenv("VIZ_AGENT_NEO4J_URI", "bolt://localhost:7687").strip()
        user = os.getenv("VIZ_AGENT_NEO4J_USER", "neo4j").strip()
        password = os.getenv("VIZ_AGENT_NEO4J_PASSWORD", "").strip()
        if not password:
            logger.warning("Neo4j enabled but VIZ_AGENT_NEO4J_PASSWORD is empty; graph write disabled")
            return None
        return cls(uri=uri, user=user, password=password)

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def ping(self) -> bool:
        with self.driver.session() as session:
            return bool(session.run("RETURN 1 AS ok").single())

    def create_nodes(self, nodes: Iterable[Dict[str, Any]]) -> None:
        query = """
        UNWIND $nodes AS node
        MERGE (n:Generic {id: node.id})
        SET n += node
        """
        with self.driver.session() as session:
            session.run(query, nodes=list(nodes))

    def create_relationships(self, rels: Iterable[Dict[str, Any]]) -> None:
        query = """
        UNWIND $rels AS rel
        MATCH (s:Generic {id: rel.source_id})
        MATCH (t:Generic {id: rel.target_id})
        MERGE (s)-[r:REL {type: rel.type}]->(t)
        SET r += rel
        """
        with self.driver.session() as session:
            session.run(query, rels=list(rels))

    def query_graph(self, cypher: str) -> List[Dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(cypher)
            return [record.data() for record in result]

    def upsert_payload(self, nodes: Iterable[Dict[str, Any]], relationships: Iterable[Dict[str, Any]]) -> None:
        self.create_nodes(nodes)
        self.create_relationships(relationships)

    @staticmethod
    def _id(prefix: str, value: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in {"_", "-", ":", "."} else "_" for ch in str(value))
        return f"{prefix}:{safe}"

    @staticmethod
    def _node(node_id: str, node_type: str, **attrs: Any) -> Dict[str, Any]:
        """Build a node with both `type` and legacy `label` fields for compatibility."""
        payload: Dict[str, Any] = {"id": node_id, "type": node_type, "label": node_type}
        payload.update(attrs)
        return payload

    @classmethod
    def build_payload(
        cls,
        semantic_model,
        lineage,
        mappings: List[Dict[str, Any]] | None = None,
        ontology_terms: List[str] | None = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        nodes: List[Dict[str, Any]] = []
        rels: List[Dict[str, Any]] = []

        for table in getattr(lineage, "tables", []):
            table_id = cls._id("table", table.name)
            nodes.append(cls._node(table_id, "Table", name=table.name, schema=table.schema))
            for col in table.columns:
                col_id = cls._id("column", f"{table.name}.{col.name}")
                nodes.append(
                    cls._node(
                        col_id,
                        "Column",
                        name=col.name,
                        table=table.name,
                        role=col.role,
                        pbi_type=col.pbi_type,
                    )
                )
                rels.append({"source_id": table_id, "target_id": col_id, "type": "HAS_COLUMN"})

        for join in getattr(lineage, "joins", []):
            left_id = cls._id("table", join.left_table)
            right_id = cls._id("table", join.right_table)
            rels.append(
                {
                    "source_id": left_id,
                    "target_id": right_id,
                    "type": "JOINS_TO",
                    "join_type": join.type,
                    "left_col": join.left_col,
                    "right_col": join.right_col,
                }
            )

        for measure in getattr(semantic_model, "measures", []):
            measure_id = cls._id("measure", measure.name)
            nodes.append(
                cls._node(
                    measure_id,
                    "Measure",
                    name=measure.name,
                    expression=measure.expression,
                )
            )
            for src in getattr(measure, "source_columns", []) or []:
                col_id = cls._id("column", f"{src.table}.{src.column}")
                rels.append({"source_id": measure_id, "target_id": col_id, "type": "DERIVED_FROM"})

        for term in ontology_terms or []:
            term_id = cls._id("term", term)
            nodes.append(cls._node(term_id, "BusinessTerm", name=term))

        for mapping in mappings or []:
            col_name = mapping.get("column")
            term = mapping.get("mapped_business_term")
            if not col_name or not term:
                continue
            table_name = None
            for table in getattr(lineage, "tables", []):
                if any(c.name == col_name for c in table.columns):
                    table_name = table.name
                    break
            col_id = cls._id("column", f"{table_name}.{col_name}" if table_name else col_name)
            term_id = cls._id("term", term)
            rels.append(
                {
                    "source_id": col_id,
                    "target_id": term_id,
                    "type": "MAPPED_TO",
                    "confidence": float(mapping.get("confidence", 0.0) or 0.0),
                    "method": str(mapping.get("method", "unknown")),
                }
            )

        # Deduplicate nodes and relationships to keep payload stable across runs.
        uniq_nodes: Dict[str, Dict[str, Any]] = {node["id"]: node for node in nodes if node.get("id")}
        uniq_rels: Dict[str, Dict[str, Any]] = {}
        for rel in rels:
            key = f"{rel.get('source_id')}|{rel.get('type')}|{rel.get('target_id')}"
            uniq_rels[key] = rel

        return {
            "nodes": list(uniq_nodes.values()),
            "relationships": list(uniq_rels.values()),
        }
