"""
ValidationHook: Integrates with Validation Agent for continuous validation
"""
from typing import Any, Dict

class ValidationHook:
    def __init__(self, validation_agent=None):
        self.validation_agent = validation_agent

    def validate(self, tool_model: Dict) -> list:
        issues: list[dict] = []

        if not isinstance(tool_model, dict):
            return [
                {
                    "severity": "error",
                    "code": "P4_V001",
                    "message": "Transformed model must be a dictionary.",
                    "field": "tool_model",
                }
            ]

        if "error" in tool_model:
            issues.append(
                {
                    "severity": "error",
                    "code": "P4_V002",
                    "message": "Transformation output contains an 'error' key.",
                    "field": "error",
                }
            )

        datasets = tool_model.get("datasets")
        visuals = tool_model.get("visuals")

        if datasets is not None and not isinstance(datasets, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P4_V003",
                    "message": "'datasets' must be a list when provided.",
                    "field": "datasets",
                }
            )

        if visuals is not None and not isinstance(visuals, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P4_V004",
                    "message": "'visuals' must be a list when provided.",
                    "field": "visuals",
                }
            )

        if (
            isinstance(datasets, list)
            and isinstance(visuals, list)
            and not datasets
            and not visuals
        ):
            issues.append(
                {
                    "severity": "warning",
                    "code": "P4_V005",
                    "message": "Transformation output has no datasets and no visuals.",
                    "field": "tool_model",
                }
            )

        if self.validation_agent and hasattr(self.validation_agent, "validate"):
            try:
                external = self.validation_agent.validate(tool_model)
                if isinstance(external, list):
                    issues.extend(external)
                elif isinstance(external, dict):
                    issues.append(external)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(
                    {
                        "severity": "warning",
                        "code": "P4_V900",
                        "message": f"External validation agent failed: {exc}",
                        "field": "validation_agent",
                    }
                )

        return issues
