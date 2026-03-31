"""
ValidationHook: Integrates with Validation Agent for continuous validation
"""
from typing import Any, Dict

class ValidationHook:
    def __init__(self, validation_agent=None):
        self.validation_agent = validation_agent

    def validate(self, result: Dict) -> list:
        issues: list[dict] = []

        if not isinstance(result, dict):
            return [
                {
                    "severity": "error",
                    "code": "P1_V001",
                    "message": "Parsing result must be a dictionary.",
                    "field": "result",
                }
            ]

        dashboards = result.get("dashboards")
        visuals = result.get("visuals")
        bindings = result.get("bindings")

        if dashboards is None:
            issues.append(
                {
                    "severity": "error",
                    "code": "P1_V002",
                    "message": "Missing required key 'dashboards' in parsing output.",
                    "field": "dashboards",
                }
            )
        elif not isinstance(dashboards, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P1_V003",
                    "message": "'dashboards' must be a list.",
                    "field": "dashboards",
                }
            )
        elif not dashboards:
            issues.append(
                {
                    "severity": "warning",
                    "code": "P1_V004",
                    "message": "No dashboards parsed.",
                    "field": "dashboards",
                }
            )

        if visuals is not None and not isinstance(visuals, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P1_V005",
                    "message": "'visuals' must be a list when provided.",
                    "field": "visuals",
                }
            )

        if bindings is not None and not isinstance(bindings, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P1_V006",
                    "message": "'bindings' must be a list when provided.",
                    "field": "bindings",
                }
            )

        if self.validation_agent and hasattr(self.validation_agent, "validate"):
            try:
                external = self.validation_agent.validate(result)
                if isinstance(external, list):
                    issues.extend(external)
                elif isinstance(external, dict):
                    issues.append(external)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(
                    {
                        "severity": "warning",
                        "code": "P1_V900",
                        "message": f"External validation agent failed: {exc}",
                        "field": "validation_agent",
                    }
                )

        return issues
