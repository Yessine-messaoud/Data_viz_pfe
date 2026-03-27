from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Column(BaseModel):
    """Universal column metadata for extraction, profiling, and catalog usage."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    type: str
    table: str
    nullable: bool | None = None
    is_used_in_dashboard: bool = False
    role: Literal["dimension", "measure", "unknown"] = "unknown"
    distinct_count: int | None = None
    null_ratio: float | None = None


class Table(BaseModel):
    """Universal table metadata containing all available columns."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    schema_name: str | None = None
    columns: list[Column]
    row_count: int | None = None
    is_used_in_dashboard: bool = False


class Relationship(BaseModel):
    """Relationship between two tables used by lineage and model navigation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    type: Literal["foreign_key", "inferred_suffix", "inferred_name"]


class MetadataModel(BaseModel):
    """Top-level metadata container emitted by phase 0 extraction."""

    model_config = ConfigDict(extra="forbid", strict=True)

    source_type: Literal["hyper", "live_sql", "rdl_live"]
    source_path: str
    tables: list[Table]
    relationships: list[Relationship]
    extraction_warnings: list[str] = Field(default_factory=list)
    metadata_version: str = "v1"
