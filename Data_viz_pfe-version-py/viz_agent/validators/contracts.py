from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ValidatorType = Literal["syntax", "semantic", "structural", "inter_phase"]
Severity = Literal["warning", "error"]


class ValidationIssueV2(BaseModel):
    type: ValidatorType
    severity: Severity
    message: str
    location: str = ""
    suggestion: str = ""
    code: str = ""


class QualityScore(BaseModel):
    syntax_score: float = 100.0
    semantic_score: float = 100.0
    structural_score: float = 100.0
    global_score: float = 100.0


class ValidationEngineReport(BaseModel):
    phase: str
    retries: int = 0
    issues: list[ValidationIssueV2] = Field(default_factory=list)
    score: QualityScore = Field(default_factory=QualityScore)
    can_proceed: bool = True
    fixes_applied: list[str] = Field(default_factory=list)
    fixed_output: dict[str, Any] = Field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

