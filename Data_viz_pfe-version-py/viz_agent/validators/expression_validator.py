from __future__ import annotations

from viz_agent.models.validation import Issue


class ExpressionValidator:
    def validate_expression(self, expression: str) -> list[Issue]:
        issues: list[Issue] = []
        candidate = expression.strip()

        if not candidate:
            issues.append(Issue(code="E_EMPTY", severity="error", message="Expression vide"))
            return issues

        if not candidate.startswith("="):
            issues.append(
                Issue(
                    code="E_PREFIX",
                    severity="error",
                    message="Expression RDL doit commencer par '='",
                )
            )

        if candidate.count("(") != candidate.count(")"):
            issues.append(
                Issue(
                    code="E_PAREN",
                    severity="error",
                    message="Parentheses non equilibrees",
                )
            )

        if "__UNTRANSLATABLE__" in candidate:
            issues.append(
                Issue(
                    code="E_UNTRANSLATABLE",
                    severity="warning",
                    message="Expression marquee intraduisible",
                )
            )

        return issues
