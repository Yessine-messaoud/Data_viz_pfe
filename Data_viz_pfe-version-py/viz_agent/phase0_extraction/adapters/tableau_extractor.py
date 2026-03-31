from __future__ import annotations

from viz_agent.phase0_extraction.adapters.base_extractor import BaseExtractor


class TableauExtractor(BaseExtractor):
    """Tableau extractor stub for .twb/.twbx extract and live modes."""

    def detect_mode(self, source_path: str) -> str:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")

    def extract_raw(self, source_path: str) -> dict:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")

    def extract_used_columns(self, source_path: str) -> set[tuple[str, str]]:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")
