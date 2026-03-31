from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    fix: str = ""
    auto_fix: str = ""


class ValidationReport(BaseModel):
    score: int = 100
    errors: list[Issue] = Field(default_factory=list)
    warnings: list[Issue] = Field(default_factory=list)
    can_proceed: bool = True
