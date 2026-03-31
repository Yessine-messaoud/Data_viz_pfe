from __future__ import annotations

import logging
import os
from pathlib import Path

from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook
from viz_agent.phase2_semantic.fact_table_detector import detect_fact_table, filter_fk_measures
from viz_agent.phase2_semantic.graph import SemanticGraph
from viz_agent.phase2_semantic.join_resolver import JoinResolver
from viz_agent.phase2_semantic.profiling import ColumnProfiler
from viz_agent.phase2_semantic.schema_mapper import TableauSchemaMapper
from viz_agent.phase2_semantic.semantic_enricher import SemanticEnricher
from viz_agent.phase2_semantic.semantic_merger import SemanticMerger
from viz_agent.phase2_semantic.ontology import OntologyLoader
from viz_agent.phase2_semantic.mapping import SemanticMappingEngine

logger = logging.getLogger(__name__)


class HybridSemanticLayer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.profiler = ColumnProfiler()

    def enrich(self, workbook: ParsedWorkbook, intent=None):
        semantic_model, lineage, _ = self.enrich_with_artifacts(workbook, intent)
        return semantic_model, lineage

    def enrich_with_artifacts(self, workbook: ParsedWorkbook, intent=None):
        schema_map = TableauSchemaMapper().map(workbook)
        joins = JoinResolver().resolve(workbook.datasources)

        # Profiling (non bloquant): utilise les frames extraites (Hyper/CSV) si disponibles.
        try:
            all_frames = {}
            if hasattr(workbook, "data_registry") and workbook.data_registry:
                all_frames = workbook.data_registry.all_frames()
            column_profiles = {}
            for table_name, frame in all_frames.items():
                column_profiles[table_name] = self.profiler.profile_dataset(table_name, frame)
            if column_profiles:
                logger.info("Profiling complete for %d tables", len(column_profiles))
        except Exception as exc:  # pragma: no cover (defensive)
            logger.warning("Profiling skipped due to error: %s", exc)

        llm_enrichment = SemanticEnricher(self.llm_client).enrich(workbook, schema_map)

        semantic_model = SemanticMerger().merge(schema_map, llm_enrichment)
        semantic_model.fact_table = detect_fact_table(schema_map.tables, joins)
        semantic_model.measures = filter_fk_measures(semantic_model.measures)

        # Ontology + mapping hybrid (heuristics + embedding + LLM validation)
        ontology = OntologyLoader(self._resolve_ontology_path()).load()
        mapping_engine = SemanticMappingEngine(ontology)
        mapped_columns = []
        mapping_payload = []
        try:
            all_cols = [c.name for t in schema_map.tables for c in getattr(t, "columns", [])]
            mapped_columns = mapping_engine.map_columns(all_cols, use_llm=True)
            mapping_payload = [m.model_dump(mode="json") for m in mapped_columns]
        except Exception as exc:  # pragma: no cover (defensive)
            logger.warning("Mapping skipped: %s", exc)

        lineage = DataLineageSpec(
            tables=schema_map.tables,
            joins=joins,
            columns_used=[],
        )

        graph_payload = SemanticGraph.build_payload(
            semantic_model,
            lineage,
            mappings=mapping_payload,
            ontology_terms=[t["name"] for t in ontology.get("terms", []) if isinstance(t.get("name"), str)],
        )
        graph_persisted = False
        graph_error = ""

        graph_client = SemanticGraph.from_env()
        if graph_client:
            try:
                graph_client.ping()
                graph_client.upsert_payload(graph_payload["nodes"], graph_payload["relationships"])
                graph_persisted = True
            except Exception as exc:  # pragma: no cover - depends on local neo4j
                graph_error = str(exc)
                logger.warning("Semantic graph persistence skipped: %s", exc)
            finally:
                graph_client.close()

        phase2_artifacts = {
            "ontology": ontology,
            "mappings": mapping_payload,
            "column_profiles": column_profiles,
            "graph": {
                "nodes": graph_payload["nodes"],
                "relationships": graph_payload["relationships"],
                "persisted": graph_persisted,
                "error": graph_error,
            },
        }

        return semantic_model, lineage, phase2_artifacts

    def _resolve_ontology_path(self) -> str | None:
        env_path = os.getenv("VIZ_AGENT_ONTOLOGY_PATH", "").strip()
        if env_path:
            return env_path

        default_path = Path(__file__).resolve().parent / "ontology" / "business_ontology.json"
        if default_path.exists():
            return str(default_path)
        return None
