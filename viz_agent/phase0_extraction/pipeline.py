from __future__ import annotations

import hashlib
from pathlib import Path

from viz_agent.phase0_extraction.models import MetadataModel

CACHE_DIR = Path(".vizagent_cache")


class MetadataExtractor:
    """Orchestrator stub for phase 0 universal metadata extraction."""

    def extract(self, source_path: str, enable_profiling: bool = False) -> MetadataModel:
        raise NotImplementedError("Sprint 1 scaffold: extraction workflow starts in Sprint 2+")

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
