from __future__ import annotations

import hashlib
import os
from pathlib import Path

from viz_agent.phase0_extraction.models import MetadataModel

CACHE_DIR = Path(".vizagent_cache")


class MetadataExtractor:
    """Orchestrator for phase 0 universal metadata extraction."""

    def extract(
        self,
        source_path: str,
        enable_profiling: bool = False,
        used_columns: set[tuple[str, str]] | None = None,
    ) -> MetadataModel:
        """
        Extraction universelle: supporte extract (hyper/csv), live_sql, rdl_live.
        - Recupere tables/colonnes.
        - Annote is_used_in_dashboard selon used_columns.
        - Retourne un MetadataModel normalise.
        """
        from viz_agent.phase0_extraction.normalization.metadata_normalizer import normalize
        from viz_agent.phase0_extraction.readers.csv_loader import CSVLoader
        from viz_agent.phase0_extraction.readers.db_connector import ConnectionConfig, DBConnector
        from viz_agent.phase0_extraction.readers.hyper_extractor import HyperExtractor
        from viz_agent.phase0_extraction.registry.data_source_registry import (
            DataSourceRegistry,
            ResolvedDataSource,
        )
        from viz_agent.phase0_extraction.relationship_detection.relationship_detector import (
            detect_from_fk,
            detect_from_heuristics,
        )

        used_columns = used_columns or set()
        registry = DataSourceRegistry()
        ext = os.path.splitext(source_path)[1].lower()
        source_type = None
        frames = {}
        sql_engine = None

        if ext == ".twbx":
            hyper = HyperExtractor()
            frames = hyper.extract_all_tables(source_path)
            csv = CSVLoader()
            frames.update(csv.extract_all_tables(source_path))
            source_type = "hyper"
        elif ext == ".csv":
            csv = CSVLoader()
            frames = csv.extract_all_tables(source_path)
            source_type = "csv"
        elif ext == ".rdl":
            # RDL direct (stub): extraction readers/adapters still to be connected.
            source_type = "rdl_live"
        elif ext in (".db", ".sqlite", ".sql", ".mdf"):
            db = DBConnector()
            config = ConnectionConfig(type="sqlite", database=source_path)
            frames = db.extract_all_tables(config)
            source_type = "live_sql"
            if ext in (".db", ".sqlite"):
                from sqlalchemy import create_engine

                sql_engine = create_engine(f"sqlite:///{source_path}")
        else:
            raise ValueError(f"Format non supporte: {ext}")

        registry.register(
            os.path.basename(source_path),
            ResolvedDataSource(
                name=os.path.basename(source_path),
                source_type=source_type,
                frames=frames,
                connection_config={"path": source_path, "type": source_type},
            ),
        )

        raw: dict = {"tables": [], "relationships": []}
        for table_name, df in frames.items():
            columns = []
            for col in df.columns:
                is_used = (table_name, col) in used_columns
                distinct_count = int(df[col].nunique()) if enable_profiling else None
                null_ratio = float(df[col].isnull().mean()) if enable_profiling else None
                columns.append(
                    {
                        "name": col,
                        "type": str(df[col].dtype),
                        "table": table_name,
                        "is_used_in_dashboard": is_used,
                        "distinct_count": distinct_count,
                        "null_ratio": null_ratio,
                    }
                )
            raw["tables"].append({"name": table_name, "columns": columns, "row_count": int(len(df))})

        model = normalize(
            raw,
            used_columns,
            source_type=source_type,
            source_path=source_path,
        )

        relationships = []
        if sql_engine is not None:
            relationships.extend(detect_from_fk(sql_engine))
        relationships.extend(detect_from_heuristics(model.tables))
        model.relationships = self._dedupe_relationships(relationships)
        return model

    def _detect_format(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext in (".twbx", ".twb"):
            return "tableau"
        if ext == ".rdl":
            return "rdl"
        raise ValueError(f"Format non supporte : {ext}")

    def _cache_key(self, source_path: str) -> str:
        mtime = Path(source_path).stat().st_mtime
        return hashlib.md5(f"{source_path}:{mtime}".encode("utf-8")).hexdigest()

    def _load_cache(self, key: str) -> MetadataModel | None:
        cache_file = CACHE_DIR / f"{key}.json"
        if not cache_file.exists():
            return None
        return MetadataModel.model_validate_json(cache_file.read_text(encoding="utf-8"))

    def _save_cache(self, key: str, model: MetadataModel) -> None:
        CACHE_DIR.mkdir(exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(model.model_dump_json(), encoding="utf-8")

    @staticmethod
    def _dedupe_relationships(relationships):
        deduped = []
        seen = set()
        for rel in relationships:
            key = (rel.source_table, rel.source_column, rel.target_table, rel.target_column, rel.type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(rel)
        return deduped
