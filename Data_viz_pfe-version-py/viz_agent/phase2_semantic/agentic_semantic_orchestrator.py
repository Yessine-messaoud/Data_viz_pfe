from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, is_dataclass
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from viz_agent.models.abstract_spec import DataLineageSpec, Measure, ParsedWorkbook
from viz_agent.phase2_semantic.fact_table_detector import detect_fact_table, filter_fk_measures
from viz_agent.phase2_semantic.graph import SemanticGraph
from viz_agent.phase2_semantic.join_resolver import JoinResolver
from viz_agent.phase2_semantic.mapping import SemanticMappingEngine
from viz_agent.phase2_semantic.ontology import OntologyLoader
from viz_agent.phase2_semantic.profiling import ColumnProfiler
from viz_agent.phase2_semantic.schema_mapper import TableauSchemaMapper
from viz_agent.phase2_semantic.semantic import ConfidenceEngine, SemanticCache, SemanticGraphBuilder, SemanticRouter
from viz_agent.phase2_semantic.semantic.cache import stable_semantic_cache_key
from viz_agent.phase2_semantic.semantic_enricher import SemanticEnricher
from viz_agent.phase2_semantic.semantic_merger import SemanticMerger

logger = logging.getLogger(__name__)


@dataclass
class _EnrichmentResult:
    suggested_measures: list[Measure]
    column_labels: dict[str, str]
    hierarchies: list[dict[str, Any]]
    column_roles: dict[str, str]


class AgenticSemanticOrchestrator:
    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client
        self.profiler = ColumnProfiler()
        self.threshold = float(os.getenv("VIZ_AGENT_SEMANTIC_CONFIDENCE_THRESHOLD", "0.75"))
        self.cache_ttl_seconds = int(os.getenv("VIZ_AGENT_SEMANTIC_CACHE_TTL_SECONDS", "21600"))
        self.cache_dir = Path(os.getenv("VIZ_AGENT_SEMANTIC_CACHE_DIR", ".vizagent_cache/phase2_semantic"))
        self.cache = SemanticCache(cache_dir=self.cache_dir, ttl_seconds=self.cache_ttl_seconds)
        self.router = SemanticRouter(threshold=self.threshold)
        self.confidence_engine = ConfidenceEngine(threshold=self.threshold)

    def run(self, workbook: ParsedWorkbook, intent=None):
        cache_key = self._fingerprint(workbook, intent)
        cache_payload = self.cache.get_cache(cache_key)
        if cache_payload:
            semantic_model, lineage, artifacts = self._deserialize_payload(cache_payload)
            cached_orchestration = artifacts.get("orchestration", {}) if isinstance(artifacts, dict) else {}
            previous_path = str(cached_orchestration.get("selected_path", "unknown"))
            artifacts["orchestration"] = {
                **cached_orchestration,
                "selected_path": "cache",
                "cached_from": previous_path,
                "llm_selection_order": ["mistral_api", "gemini_api", "ollama_local"],
                "threshold": self.threshold,
                "cache_key": cache_key,
            }
            return semantic_model, lineage, artifacts

        fast_result = self._run_fast_path(workbook)
        selected_path, selected_result = self.router.route(
            cache_hit=None,
            fast_result=fast_result,
            llm_result_factory=lambda: self._run_fallback_path(workbook),
        )

        if selected_path in {"fast", "fallback"}:
            self._store_cache(cache_key, *selected_result)

        return selected_result

    def _run_fast_path(self, workbook: ParsedWorkbook):
        schema_map = TableauSchemaMapper().map(workbook)
        joins = JoinResolver().resolve(
            workbook.datasources,
            tableau_relationships=list(getattr(workbook, "tableau_relationships", []) or []),
            table_name_map=dict(getattr(schema_map, "physical_to_logical", {}) or {}),
        )
        column_profiles = self._profile_columns(workbook)

        enrichment = self._fast_enrichment(workbook, schema_map)
        semantic_model = SemanticMerger().merge(schema_map, enrichment)
        semantic_model.fact_table = detect_fact_table(schema_map.tables, joins)
        semantic_model.measures = filter_fk_measures(semantic_model.measures)

        ontology = OntologyLoader(self._resolve_ontology_path()).load()
        mapping_payload = self._build_mappings(schema_map, ontology, use_llm=False)

        lineage = DataLineageSpec(
            tables=schema_map.tables,
            joins=joins,
            columns_used=[],
        )

        graph_payload = SemanticGraphBuilder.build(
            semantic_model,
            lineage,
            workbook,
            mappings=mapping_payload,
        )
        graph_persisted, graph_error = self._persist_graph(graph_payload)

        scoring = self._compute_confidence(
            heuristic_score=self._heuristic_score(schema_map, semantic_model, joins),
            profiling_score=self._profiling_score(schema_map, column_profiles),
            ontology_score=self._ontology_score(mapping_payload),
            llm_score=0.0,
            path="fast",
        )

        artifacts = {
            "ontology": ontology,
            "mappings": mapping_payload,
            "column_profiles": column_profiles,
            "graph": {
                "nodes": graph_payload["nodes"],
                "relationships": graph_payload["relationships"],
                "persisted": graph_persisted,
                "error": graph_error,
            },
            "orchestration": {
                "selected_path": "fast",
                "llm_provider": "none",
                "llm_selection_order": ["mistral_api", "gemini_api", "ollama_local"],
                "threshold": self.threshold,
                **scoring,
            },
        }
        return semantic_model, lineage, artifacts

    def _run_fallback_path(self, workbook: ParsedWorkbook):
        schema_map = TableauSchemaMapper().map(workbook)
        joins = JoinResolver().resolve(
            workbook.datasources,
            tableau_relationships=list(getattr(workbook, "tableau_relationships", []) or []),
            table_name_map=dict(getattr(schema_map, "physical_to_logical", {}) or {}),
        )
        column_profiles = self._profile_columns(workbook)

        llm_enrichment = SemanticEnricher(self.llm_client).enrich(workbook, schema_map)
        llm_provider = str(getattr(llm_enrichment, "llm_provider", "unknown") or "unknown")
        llm_error = str(getattr(llm_enrichment, "llm_error", "") or "")
        semantic_model = SemanticMerger().merge(schema_map, llm_enrichment)
        semantic_model.fact_table = detect_fact_table(schema_map.tables, joins)
        semantic_model.measures = filter_fk_measures(semantic_model.measures)

        ontology = OntologyLoader(self._resolve_ontology_path()).load()
        mapping_payload = self._build_mappings(schema_map, ontology, use_llm=True)

        lineage = DataLineageSpec(
            tables=schema_map.tables,
            joins=joins,
            columns_used=[],
        )

        graph_payload = SemanticGraphBuilder.build(
            semantic_model,
            lineage,
            workbook,
            mappings=mapping_payload,
        )
        graph_persisted, graph_error = self._persist_graph(graph_payload)

        scoring = self._compute_confidence(
            heuristic_score=self._heuristic_score(schema_map, semantic_model, joins),
            profiling_score=self._profiling_score(schema_map, column_profiles),
            ontology_score=self._ontology_score(mapping_payload),
            llm_score=self._llm_score(mapping_payload, llm_enrichment),
            path="fallback",
        )

        artifacts = {
            "ontology": ontology,
            "mappings": mapping_payload,
            "column_profiles": column_profiles,
            "graph": {
                "nodes": graph_payload["nodes"],
                "relationships": graph_payload["relationships"],
                "persisted": graph_persisted,
                "error": graph_error,
            },
            "orchestration": {
                "selected_path": "fallback",
                "llm_provider": llm_provider,
                "llm_error": llm_error,
                "llm_selection_order": ["mistral_api", "gemini_api", "ollama_local"],
                "threshold": self.threshold,
                **scoring,
            },
        }
        return semantic_model, lineage, artifacts

    def _profile_columns(self, workbook: ParsedWorkbook) -> dict[str, Any]:
        column_profiles: dict[str, Any] = {}
        try:
            all_frames = {}
            if hasattr(workbook, "data_registry") and workbook.data_registry:
                all_frames = workbook.data_registry.all_frames()
            for table_name, frame in all_frames.items():
                column_profiles[table_name] = self.profiler.profile_dataset(table_name, frame)
        except Exception as exc:  # pragma: no cover
            logger.warning("Profiling skipped due to error: %s", exc)
        return column_profiles

    def _fast_enrichment(self, workbook: ParsedWorkbook, schema_map) -> _EnrichmentResult:
        measures: list[Measure] = []
        seen: set[str] = set()

        for calc in getattr(workbook, "calculated_fields", []) or []:
            name = str(getattr(calc, "name", "") or "").strip()
            expression = str(getattr(calc, "expression", "") or "").strip()
            if not name or not expression:
                continue
            key = name.lower()
            if key in seen:
                continue
            measures.append(Measure(name=name, expression=expression, tableau_expression=name))
            seen.add(key)

        keywords = ("amount", "sales", "revenue", "profit", "cost", "price", "qty", "quantity", "count", "tax")
        for table in getattr(schema_map, "tables", []) or []:
            for col in getattr(table, "columns", []) or []:
                col_name = str(getattr(col, "name", "") or "").strip()
                if not col_name:
                    continue
                lowered = col_name.lower()
                if lowered.endswith("key") or lowered.endswith("_id") or lowered == "id":
                    continue
                role = str(getattr(col, "role", "unknown") or "unknown").lower()
                if role != "measure" and not any(k in lowered for k in keywords):
                    continue
                measure_name = f"Sum {col_name}"
                key = measure_name.lower()
                if key in seen:
                    continue
                measures.append(Measure(name=measure_name, expression=f"SUM([{col_name}])", tableau_expression=col_name))
                seen.add(key)

        if not measures:
            measures.append(Measure(name="Row Count", expression="COUNT(*)", tableau_expression="row_count"))

        return _EnrichmentResult(
            suggested_measures=measures,
            column_labels={},
            hierarchies=[],
            column_roles={},
        )

    def _build_mappings(self, schema_map, ontology: dict[str, Any], use_llm: bool) -> list[dict[str, Any]]:
        mapping_engine = SemanticMappingEngine(ontology)
        all_cols = [c.name for t in schema_map.tables for c in getattr(t, "columns", [])]
        mapped_columns = mapping_engine.map_columns(all_cols, use_llm=use_llm)
        return [m.model_dump(mode="json") for m in mapped_columns]

    def _persist_graph(self, graph_payload: dict[str, Any]) -> tuple[bool, str]:
        graph_persisted = False
        graph_error = ""
        graph_client = SemanticGraph.from_env()
        if graph_client:
            try:
                graph_client.ping()
                graph_client.upsert_payload(graph_payload["nodes"], graph_payload["relationships"])
                graph_persisted = True
            except Exception as exc:  # pragma: no cover
                graph_error = str(exc)
                logger.warning("Semantic graph persistence skipped: %s", exc)
            finally:
                graph_client.close()
        return graph_persisted, graph_error

    def _heuristic_score(self, schema_map, semantic_model, joins) -> float:
        tables = len(getattr(schema_map, "tables", []) or [])
        measures = len(getattr(semantic_model, "measures", []) or [])
        join_count = len(joins or [])
        table_score = 1.0 if tables > 0 else 0.0
        measure_score = 1.0 if measures > 0 else 0.0
        join_score = 1.0 if join_count > 0 else 0.5
        return max(0.0, min(1.0, (0.4 * table_score) + (0.4 * measure_score) + (0.2 * join_score)))

    def _profiling_score(self, schema_map, column_profiles: dict[str, Any]) -> float:
        total_columns = sum(len(getattr(table, "columns", []) or []) for table in getattr(schema_map, "tables", []) or [])
        if total_columns == 0:
            return 0.0
        profiled_columns = 0
        for profiles in column_profiles.values():
            profiled_columns += len(profiles or [])
        if not column_profiles:
            return 0.5
        return max(0.0, min(1.0, profiled_columns / max(1, total_columns)))

    def _ontology_score(self, mapping_payload: list[dict[str, Any]]) -> float:
        if not mapping_payload:
            return 0.0
        confidences = [float(item.get("confidence", 0.0) or 0.0) for item in mapping_payload]
        if not confidences:
            return 0.0
        return max(0.0, min(1.0, sum(confidences) / len(confidences)))

    def _llm_score(self, mapping_payload: list[dict[str, Any]], llm_enrichment: Any) -> float:
        semantic_signal = 0.0
        if getattr(llm_enrichment, "column_labels", {}) or getattr(llm_enrichment, "hierarchies", []) or getattr(llm_enrichment, "column_roles", {}):
            semantic_signal = 1.0

        llm_mapping_confs = [
            float(item.get("confidence", 0.0) or 0.0)
            for item in mapping_payload
            if "llm" in str(item.get("method", "")).lower()
        ]
        mapping_signal = (sum(llm_mapping_confs) / len(llm_mapping_confs)) if llm_mapping_confs else 0.0
        return max(0.0, min(1.0, (0.5 * semantic_signal) + (0.5 * mapping_signal)))

    def _compute_confidence(
        self,
        heuristic_score: float,
        profiling_score: float,
        ontology_score: float,
        llm_score: float,
        path: str,
    ) -> dict[str, Any]:
        return self.confidence_engine.compute(
            heuristic_score=heuristic_score,
            profiling_score=profiling_score,
            ontology_score=ontology_score,
            llm_score=llm_score,
            path=path,
        )

    def _resolve_ontology_path(self) -> str | None:
        env_path = os.getenv("VIZ_AGENT_ONTOLOGY_PATH", "").strip()
        if env_path:
            return env_path
        default_path = Path(__file__).resolve().parent / "ontology" / "business_ontology.json"
        if default_path.exists():
            return str(default_path)
        return None

    def _fingerprint(self, workbook: ParsedWorkbook, intent: Any) -> str:
        _ = intent
        return stable_semantic_cache_key(workbook)

    def _cache_file(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def _load_cache(self, cache_key: str) -> dict[str, Any] | None:
        return self.cache.get_cache(cache_key)

    def _store_cache(self, cache_key: str, semantic_model, lineage, artifacts) -> None:
        try:
            payload = {
                "semantic_model": semantic_model.model_dump(mode="json"),
                "lineage": lineage.model_dump(mode="json"),
                "artifacts": self._to_jsonable(artifacts),
            }
            self.cache.set_cache(cache_key, payload)
        except Exception as exc:  # pragma: no cover
            logger.warning("Semantic cache write skipped: %s", exc)

    def _deserialize_payload(self, payload: dict[str, Any]):
        from viz_agent.models.abstract_spec import DataLineageSpec, SemanticModel

        semantic_model = SemanticModel.model_validate(payload.get("semantic_model", {}))
        lineage = DataLineageSpec.model_validate(payload.get("lineage", {}))
        artifacts = payload.get("artifacts", {}) if isinstance(payload.get("artifacts", {}), dict) else {}
        return semantic_model, lineage, artifacts

    def _to_jsonable(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._to_jsonable(asdict(value))
        if isinstance(value, dict):
            return {str(k): self._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable(v) for v in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "model_dump"):
            try:
                return self._to_jsonable(value.model_dump(mode="json"))
            except Exception:
                return str(value)
        if isinstance(value, Path):
            return str(value)
        return str(value)
