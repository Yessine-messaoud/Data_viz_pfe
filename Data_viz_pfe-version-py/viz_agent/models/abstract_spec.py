from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class ColumnDef(BaseModel):
    name: str
    pbi_type: str = "text"
    role: Literal["measure", "dimension", "unknown"] = "unknown"
    is_hidden: bool = False
    label: str = ""


class ColumnRef(BaseModel):
    table: str
    column: str


class ResolvedColumn(BaseModel):
    type: Literal["resolved", "expression", "measure_names_placeholder", "simple"]
    table: str
    column: str
    agg: str = "NONE"
    role: Literal["measure", "dimension", "unknown"] = "unknown"
    raw: str = ""
    needs_llm: bool = False


class JoinDef(BaseModel):
    id: str
    left_table: str
    right_table: str
    left_col: str
    right_col: str
    type: Literal["INNER", "LEFT", "RIGHT", "FULL"] = "INNER"
    pbi_cardinality: str = "ManyToOne"
    source_xml_ref: str = ""


class Measure(BaseModel):
    name: str
    expression: str
    rdl_expression: str = ""
    source_columns: list[ColumnRef] = Field(default_factory=list)
    pattern: str = ""
    template_args: dict[str, Any] = Field(default_factory=dict)
    tableau_expression: str = ""


class TableRef(BaseModel):
    id: str
    name: str
    source_name: str = ""
    schema: str = "dbo"
    columns: list[ColumnDef] = Field(default_factory=list)
    is_date_table: bool = False
    row_count: int = 0


class CalcField(BaseModel):
    name: str
    expression: str
    rdl_expression: str = ""


class Parameter(BaseModel):
    name: str
    data_type: str = "string"
    default_value: str = ""


class Filter(BaseModel):
    field: str
    operator: str = "="
    value: Any = None
    column: str = ""


class Palette(BaseModel):
    name: str
    colors: list[str] = Field(default_factory=list)


class VisualEncoding(BaseModel):
    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    detail: str | None = None


class SemanticHint(BaseModel):
    column: str
    role_hint: Literal["measure", "dimension", "unknown"] = "unknown"
    aggregation_hint: Literal["sum", "avg", "count", "none"] = "none"
    confidence: float = 0.0
    datasource_name: str = ""
    data_type: str = ""
    cardinality: int | None = None
    worksheet_role: str = ""


class ConfidenceScore(BaseModel):
    visual: float = 0.0
    encoding: float = 0.0
    datasource_linkage: float = 0.0
    overall: float = 0.0


class EnrichedLineageEntry(BaseModel):
    column: str
    used_in: str
    role: str
    datasource_name: str = ""
    confidence: float = 0.0


class DataSource(BaseModel):
    name: str
    caption: str = ""
    connection_type: str = ""
    columns: list[ColumnDef] = Field(default_factory=list)


class MeasureRef(BaseModel):
    name: str


class DataBinding(BaseModel):
    axes: dict[str, ColumnRef | MeasureRef] = Field(default_factory=dict)
    measures: list[MeasureRef] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    hierarchy: list[str] = Field(default_factory=list)
    aggregation: str = ""
    filters: list[Any] = Field(default_factory=list)
    visual_type_override: str = ""
    pending_translations: list[Any] = Field(default_factory=list)


class VisualSpec(BaseModel):
    id: str
    source_worksheet: str
    type: str = "tablix"
    rdl_type: str = "tablix"
    title: str
    position: dict[str, Any] = Field(default_factory=dict)
    data_binding: DataBinding


class DashboardPage(BaseModel):
    id: str
    name: str
    visuals: list[VisualSpec] = Field(default_factory=list)


class DashboardSpec(BaseModel):
    pages: list[DashboardPage]
    global_filters: list[Filter] = Field(default_factory=list)
    theme: dict[str, Any] = Field(default_factory=dict)


class SemanticModel(BaseModel):
    entities: list[Any] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)
    dimensions: list[Any] = Field(default_factory=list)
    hierarchies: list[Any] = Field(default_factory=list)
    relationships: list[Any] = Field(default_factory=list)
    glossary: list[Any] = Field(default_factory=list)
    fact_table: str = ""
    grain: str = ""


class VisualColumnEntry(BaseModel):
    columns: list[ColumnRef] = Field(default_factory=list)
    joins_used: list[str] = Field(default_factory=list)
    filters: list[Any] = Field(default_factory=list)


class DataLineageSpec(BaseModel):
    tables: list[TableRef] = Field(default_factory=list)
    joins: list[JoinDef] = Field(default_factory=list)
    columns_used: list[Any] = Field(default_factory=list)
    measures: list[Any] = Field(default_factory=list)
    filters_applied: list[Any] = Field(default_factory=list)
    transformations: list[Any] = Field(default_factory=list)
    visual_column_map: dict[str, VisualColumnEntry] = Field(default_factory=dict)


class BuildLogEntry(BaseModel):
    level: Literal["info", "warning", "error"]
    message: str
    timestamp: str = ""


class Worksheet(BaseModel):
    name: str
    title: str = ""
    mark_type: str
    raw_mark_type: str = ""
    rows_shelf: list[ColumnRef] = Field(default_factory=list)
    cols_shelf: list[ColumnRef] = Field(default_factory=list)
    marks_shelf: list[ColumnRef] = Field(default_factory=list)
    mark_encodings: dict[str, ColumnRef] = Field(default_factory=dict)
    filters: list[Filter] = Field(default_factory=list)
    datasource_name: str = ""
    visual_encoding: VisualEncoding = Field(default_factory=VisualEncoding)
    semantic_hints: list[SemanticHint] = Field(default_factory=list)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    enriched_lineage: list[EnrichedLineageEntry] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class TableauDashboard(BaseModel):
    name: str
    worksheets: list[str] = Field(default_factory=list)
    width: int = 1200
    height: int = 800


class ParsedWorkbook(BaseModel):
    worksheets: list[Worksheet] = Field(default_factory=list)
    datasources: list[DataSource] = Field(default_factory=list)
    dashboards: list[TableauDashboard] = Field(default_factory=list)
    calculated_fields: list[CalcField] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    color_palettes: list[Palette] = Field(default_factory=list)
    tableau_relationships: list[dict[str, Any]] = Field(default_factory=list)
    data_registry: Any = None
    visual_encoding: dict[str, VisualEncoding] = Field(default_factory=dict)
    semantic_hints: list[SemanticHint] = Field(default_factory=list)
    confidence: dict[str, ConfidenceScore] = Field(default_factory=dict)
    enriched_lineage: list[EnrichedLineageEntry] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class AbstractSpec(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "2.0.0"
    created_at: str = ""
    source_fingerprint: str = ""
    dashboard_spec: DashboardSpec
    semantic_model: SemanticModel
    data_lineage: DataLineageSpec
    rdl_datasets: list[Any] = Field(default_factory=list)
    build_log: list[BuildLogEntry] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
