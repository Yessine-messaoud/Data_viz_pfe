from __future__ import annotations

import json
from typing import Any

from viz_agent.validators.contracts import ValidationIssueV2


class SyntaxValidator:
    name = "syntax"

    def validate(self, data: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssueV2]:
        issues: list[ValidationIssueV2] = []

        try:
            json.dumps(data)
        except Exception as exc:
            issues.append(
                ValidationIssueV2(
                    type="syntax",
                    severity="error",
                    code="SX001",
                    message=f"Payload non serialisable en JSON: {exc}",
                    location="$",
                    suggestion="Convertir les objets non JSON (datetime, set, etc.) avant validation.",
                )
            )
            return issues

        if "dashboard_spec" in data:
            pages = ((data.get("dashboard_spec") or {}).get("pages") or [])
            if not isinstance(pages, list):
                issues.append(
                    ValidationIssueV2(
                        type="syntax",
                        severity="error",
                        code="SX002",
                        message="dashboard_spec.pages doit etre une liste.",
                        location="dashboard_spec.pages",
                        suggestion="Corriger la structure de page en list[].",
                    )
                )

        return issues

