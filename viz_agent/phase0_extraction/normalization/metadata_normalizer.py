from __future__ import annotations

from viz_agent.phase0_extraction.models import MetadataModel


def normalize(raw: dict, used_columns: set[tuple[str, str]]) -> MetadataModel:
    """Convert raw extracted metadata into MetadataModel."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")
