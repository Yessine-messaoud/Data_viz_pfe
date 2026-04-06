"""Enhanced visualization model with strict separation of concerns"""
from __future__ import annotations
from typing import Any, Literal, Union
from pydantic import BaseModel, Field, validator

# Strict allowed visualization types - NO "chart" fallback
VisualizationType = Literal["bar", "line", "pie", "treemap", "scatter", "table", "kpi", "map", "gantt"]

# Strict RDL rendering types mapped to specific chart types
RDLRenderingType = Literal[
    "ColumnChart",
    "BarChart", 
    "LineChart",
    "PieChart",
    "TreeMap",
    "ScatterChart",
    "Tablix",
    "Textbox",
    "Map",
]


class EncodingAxis(BaseModel):
    """Represents a data axis encoding (X, Y, Size, Color, etc.)"""
    field: str
    aggregation: Literal["SUM", "AVG", "COUNT", "MIN", "MAX", "NONE"] = "NONE"
    role: Literal["dimension", "measure"] = "dimension"


class EncodingSpec(BaseModel):
    """Strict encoding specification for a visualization"""
    x: Union[EncodingAxis, None] = None
    y: Union[EncodingAxis, None] = None
    color: Union[EncodingAxis, None] = None
    size: Union[EncodingAxis, None] = None
    details: list[EncodingAxis] = Field(default_factory=list)

    @validator("x", "y", pre=True, always=False)
    def validate_axis_present_if_needed(cls, v, values):
        """Override in subclasses to enforce axis requirements"""
        return v

    class Config:
        extra = "forbid"


class VisualizationSpec(BaseModel):
    """Business-level visualization specification"""
    type: VisualizationType
    encoding: EncodingSpec = Field(default_factory=EncodingSpec)
    title: str = ""
    description: str = ""

    @validator("type")
    def validate_type_not_generic(cls, v):
        if v == "chart":
            raise ValueError("Generic 'chart' type is not allowed. Use specific type: bar, line, pie, etc.")
        return v

    class Config:
        extra = "forbid"


class DataSpec(BaseModel):
    """Data binding specification"""
    fact_table: str
    filters: list[dict[str, Any]] = Field(default_factory=list)
    joins: list[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class RenderingSpec(BaseModel):
    """RDL-specific rendering specification"""
    rdl_type: RDLRenderingType
    chart_type: Union[Literal["Column", "Bar", "Line", "Pie", "Area", "Scatter"], None] = None
    dimensions: dict[str, Any] = Field(default_factory=dict)
    layout: dict[str, Any] = Field(default_factory=dict)

    @validator("rdl_type", "chart_type", pre=True)
    def validate_no_generic_chart(cls, v):
        if v == "chart":
            raise ValueError("Generic 'chart' RDL type is not allowed. Use specific type from allowed list.")
        return v

    class Config:
        extra = "forbid"


class VisualSpecV2(BaseModel):
    """Enhanced visual specification with strict separation of concerns"""
    id: str
    source_worksheet: str
    title: str
    
    # Clear separation of layers
    visualization: VisualizationSpec
    encoding: EncodingSpec
    data: DataSpec
    rendering: RenderingSpec
    
    position: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @validator("visualization", pre=True)
    def ensure_visualization_type_valid(cls, v):
        if isinstance(v, dict) and v.get("type") == "chart":
            raise ValueError(
                f"Invalid visualization type 'chart'. Must use specific type. "
                f"Allowed: bar, line, pie, treemap, scatter, table, kpi, map, gantt"
            )
        return v

    class Config:
        extra = "forbid"
