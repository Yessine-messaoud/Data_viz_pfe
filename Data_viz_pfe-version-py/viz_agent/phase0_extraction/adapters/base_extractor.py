from __future__ import annotations

from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Common extractor contract for source-specific adapters."""

    @abstractmethod
    def detect_mode(self, source_path: str) -> str:
        """Return one of: 'extract' | 'live_sql' | 'rdl_live'."""

    @abstractmethod
    def extract_raw(self, source_path: str) -> dict:
        """Return raw metadata payload used by the normalizer."""

    @abstractmethod
    def extract_used_columns(self, source_path: str) -> set[tuple[str, str]]:
        """Parse visuals and return referenced (table, column) pairs."""
