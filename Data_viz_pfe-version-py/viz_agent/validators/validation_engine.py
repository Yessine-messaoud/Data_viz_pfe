from __future__ import annotations

import logging
from typing import Any

from viz_agent.validators.autofix.auto_fix_engine import AutoFixEngine
from viz_agent.validators.contracts import QualityScore, ValidationEngineReport, ValidationIssueV2
from viz_agent.validators.validators.inter_phase_validator import InterPhaseValidator
from viz_agent.validators.validators.semantic_validator import SemanticValidator
from viz_agent.validators.validators.structural_validator import StructuralValidator
from viz_agent.validators.validators.syntax_validator import SyntaxValidator

logger = logging.getLogger(__name__)


class ValidationEngine:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.syntax_validator = SyntaxValidator()
        self.semantic_validator = SemanticValidator()
        self.structural_validator = StructuralValidator()
        self.inter_phase_validator = InterPhaseValidator()
        self.auto_fix_engine = AutoFixEngine()

    def validate_phase(self, phase: str, data: dict[str, Any], context: dict[str, Any] | None = None) -> ValidationEngineReport:
        context = context or {}
        candidate = dict(data)
        all_fixes: list[str] = []
        retries = 0

        # Lightweight normalization pass to keep outputs consistent even before hard errors.
        candidate, initial_fixes = self.auto_fix_engine.apply(candidate)
        all_fixes.extend(initial_fixes)

        while True:
            issues = self._collect_issues(candidate, context)
            if not self._has_errors(issues):
                score = self._compute_scores(issues)
                return ValidationEngineReport(
                    phase=phase,
                    retries=retries,
                    issues=issues,
                    score=score,
                    can_proceed=True,
                    fixes_applied=all_fixes,
                    fixed_output=candidate,
                )

            if retries >= self.max_retries:
                score = self._compute_scores(issues)
                return ValidationEngineReport(
                    phase=phase,
                    retries=retries,
                    issues=issues,
                    score=score,
                    can_proceed=False,
                    fixes_applied=all_fixes,
                    fixed_output=candidate,
                )

            candidate, fixes = self.auto_fix_engine.apply(candidate)
            if not fixes:
                score = self._compute_scores(issues)
                return ValidationEngineReport(
                    phase=phase,
                    retries=retries,
                    issues=issues,
                    score=score,
                    can_proceed=False,
                    fixes_applied=all_fixes,
                    fixed_output=candidate,
                )

            retries += 1
            all_fixes.extend(fixes)
            logger.info("Validation auto-fix round=%s fixes=%s", retries, len(fixes))

    def _collect_issues(self, data: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssueV2]:
        issues: list[ValidationIssueV2] = []
        issues.extend(self.syntax_validator.validate(data, context))
        issues.extend(self.semantic_validator.validate(data, context))
        issues.extend(self.structural_validator.validate(data, context))
        issues.extend(self.inter_phase_validator.validate(data, context))
        return issues

    def _has_errors(self, issues: list[ValidationIssueV2]) -> bool:
        return any(issue.severity == "error" for issue in issues)

    def _compute_scores(self, issues: list[ValidationIssueV2]) -> QualityScore:
        def bucket(base: float, issue_type: str) -> float:
            err = sum(1 for i in issues if i.type == issue_type and i.severity == "error")
            warn = sum(1 for i in issues if i.type == issue_type and i.severity == "warning")
            return max(0.0, base - (err * 25.0) - (warn * 8.0))

        syntax = bucket(100.0, "syntax")
        semantic = bucket(100.0, "semantic")
        structural = bucket(100.0, "structural")
        inter_phase = bucket(100.0, "inter_phase")
        global_score = round((syntax + semantic + structural + inter_phase) / 4.0, 2)

        return QualityScore(
            syntax_score=syntax,
            semantic_score=semantic,
            structural_score=structural,
            global_score=global_score,
        )
