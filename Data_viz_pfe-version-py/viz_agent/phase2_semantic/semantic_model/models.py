from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ColumnProfileModel(BaseModel):
    name: str
    inferred_dtype: str
    role: str
    distinct_count: int
    null_ratio: float
    sample_values: List[Any] = Field(default_factory=list)


class SemanticMappingModel(BaseModel):
    column: str
    mapped_business_term: Optional[str] = None
    confidence: float = 0.0
    method: str = "heuristic"
    details: dict[str, Any] = Field(default_factory=dict)


class SemanticModelV2(BaseModel):
    column_profiles: List[ColumnProfileModel] = Field(default_factory=list)
    mappings: List[SemanticMappingModel] = Field(default_factory=list)
    ontology_terms: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
