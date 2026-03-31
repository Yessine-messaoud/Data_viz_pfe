"""
ValidationHook: Integrates with Validation Agent for continuous validation
"""
from typing import Any, Dict

class ValidationHook:
    def __init__(self, validation_agent=None):
        self.validation_agent = validation_agent

    def validate(self, graph: Dict) -> list:
        issues: list[dict] = []

        if not isinstance(graph, dict):
            return [
                {
                    "severity": "error",
                    "code": "P2_V001",
                    "message": "Semantic graph must be a dictionary.",
                    "field": "graph",
                }
            ]

        if not graph:
            issues.append(
                {
                    "severity": "error",
                    "code": "P2_V002",
                    "message": "Semantic graph is empty.",
                    "field": "graph",
                }
            )

        entities = graph.get("entities")
        measures = graph.get("measures")
        relations = graph.get("relations", graph.get("relationships"))

        if entities is not None and not isinstance(entities, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P2_V003",
                    "message": "'entities' must be a list when provided.",
                    "field": "entities",
                }
            )

        if measures is not None and not isinstance(measures, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P2_V004",
                    "message": "'measures' must be a list when provided.",
                    "field": "measures",
                }
            )

        if relations is not None and not isinstance(relations, list):
            issues.append(
                {
                    "severity": "error",
                    "code": "P2_V005",
                    "message": "'relations'/'relationships' must be a list when provided.",
                    "field": "relations",
                }
            )

        if (
            isinstance(entities, list)
            and isinstance(measures, list)
            and not entities
            and not measures
        ):
            issues.append(
                {
                    "severity": "warning",
                    "code": "P2_V006",
                    "message": "Semantic graph contains no entities and no measures.",
                    "field": "graph",
                }
            )

        if self.validation_agent and hasattr(self.validation_agent, "validate"):
            try:
                external = self.validation_agent.validate(graph)
                if isinstance(external, list):
                    issues.extend(external)
                elif isinstance(external, dict):
                    issues.append(external)
            except Exception as exc:  # pragma: no cover - defensive
                issues.append(
                    {
                        "severity": "warning",
                        "code": "P2_V900",
                        "message": f"External validation agent failed: {exc}",
                        "field": "validation_agent",
                    }
                )

        return issues
