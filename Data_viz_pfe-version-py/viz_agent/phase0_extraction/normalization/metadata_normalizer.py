from __future__ import annotations

from viz_agent.phase0_extraction.models import MetadataModel


def normalize(
    raw: dict,
    used_columns: set[tuple[str, str]],
    *,
    source_type: str,
    source_path: str,
) -> MetadataModel:
    """Convert raw extracted metadata into MetadataModel (Pydantic strict)."""
    from viz_agent.phase0_extraction.models import Column, Table, Relationship, MetadataModel
    tables = []
    for t in raw.get("tables", []):
        columns = [Column(**c) for c in t.get("columns", [])]
        tables.append(Table(name=t["name"], columns=columns, row_count=t.get("row_count")))
    relationships = [Relationship(**r) for r in raw.get("relationships", [])]
    return MetadataModel(
        source_type=source_type,
        source_path=source_path,
        tables=tables,
        relationships=relationships,
        extraction_warnings=[],
        metadata_version="v1"
    )
