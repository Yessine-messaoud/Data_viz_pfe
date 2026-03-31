from __future__ import annotations

import hashlib
from pathlib import Path

from viz_agent.phase0_extraction.models import MetadataModel

CACHE_DIR = Path(".vizagent_cache")


class MetadataExtractor:
    """Orchestrator stub for phase 0 universal metadata extraction."""

    def extract(self, source_path: str, enable_profiling: bool = False, used_columns: set[tuple[str, str]] = None) -> MetadataModel:
        """
        Extraction universelle : supporte extract (hyper/csv), live_sql, rdl_live.
        - Récupère toutes les tables/colonnes.
        - Annote is_used_in_dashboard selon used_columns.
        - Retourne un MetadataModel Pydantic normalisé.
        """
        from viz_agent.phase0_extraction.readers.csv_loader import CSVLoader
        from viz_agent.phase0_extraction.readers.hyper_extractor import HyperExtractor
        from viz_agent.phase0_extraction.readers.db_connector import DBConnector, ConnectionConfig
        from viz_agent.phase0_extraction.registry.data_source_registry import DataSourceRegistry, ResolvedDataSource
        from viz_agent.phase0_extraction.normalization.metadata_normalizer import normalize
        import os
        import pandas as pd
        registry = DataSourceRegistry()
        ext = os.path.splitext(source_path)[1].lower()
        source_type = None
        frames = {}
        if ext == ".twbx":
            # Extraction Hyper/CSV
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
            # RDL direct (stub)
            # TODO: brancher RDLExtractor/adapters
            source_type = "rdl_live"
            # frames = ...
        elif ext in (".db", ".sqlite", ".sql", ".mdf"):
            # SQL direct
            db = DBConnector()
            config = ConnectionConfig(type="sqlite", database=source_path)
            frames = db.extract_all_tables(config)
            source_type = "live_sql"
        else:
            raise ValueError(f"Format non supporté : {ext}")
        # Register source
        registry.register(os.path.basename(source_path), ResolvedDataSource(
            name=os.path.basename(source_path),
            source_type=source_type,
            frames=frames,
            connection_config={"path": source_path, "type": source_type}
        ))
        # Build raw metadata for normalization
        raw = {}
        raw["tables"] = []
        for table_name, df in frames.items():
            columns = []
            for col in df.columns:
                is_used = False
                if used_columns:
                    is_used = (table_name, col) in used_columns
                # Profiling optionnel (distinct_count, null_ratio)
                distinct_count = int(df[col].nunique()) if enable_profiling else None
                null_ratio = float(df[col].isnull().mean()) if enable_profiling else None
                columns.append({
                    "name": col,
                    "type": str(df[col].dtype),
                    "table": table_name,
                    "is_used_in_dashboard": is_used,
                    "distinct_count": distinct_count,
                    "null_ratio": null_ratio,
                })
            raw["tables"].append({
                "name": table_name,
                "columns": columns,
                "row_count": int(len(df)),
            })
        # Détection des relations (FK + heuristiques)
        from viz_agent.phase0_extraction.relationship_detection.relationship_detector import detect_from_fk, detect_from_heuristics
        relationships = []
        # FK SQL (si applicable)
        # TODO: brancher engine si SQL
        # relationships += detect_from_fk(engine)
        # Heuristiques sur les noms
        # relationships += detect_from_heuristics(...)
        raw["relationships"] = relationships
        # Normalisation Pydantic stricte
        model = normalize(raw, used_columns or set())
        model.source_type = source_type
        model.source_path = source_path
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
