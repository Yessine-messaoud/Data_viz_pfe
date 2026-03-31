"""
LineageHook: Integrates with Lineage Agent for continuous lineage capture
"""
from datetime import datetime, timezone
from typing import Any, Dict

class LineageHook:
    def __init__(self, lineage_agent=None):
        self.lineage_agent = lineage_agent

    def capture(self, graph: Dict) -> list:
        entities = graph.get("entities", []) if isinstance(graph, dict) else []
        measures = graph.get("measures", []) if isinstance(graph, dict) else []
        relations = graph.get("relations", graph.get("relationships", [])) if isinstance(graph, dict) else []

        event = {
            "phase": "phase2_semantic",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entities_count": len(entities) if isinstance(entities, list) else 0,
            "measures_count": len(measures) if isinstance(measures, list) else 0,
            "relations_count": len(relations) if isinstance(relations, list) else 0,
            "status": "ok" if isinstance(graph, dict) and "error" not in graph else "error",
        }
        events = [event]

        if self.lineage_agent and hasattr(self.lineage_agent, "capture"):
            try:
                external = self.lineage_agent.capture(graph)
                if isinstance(external, list):
                    events.extend(external)
                elif isinstance(external, dict):
                    events.append(external)
            except Exception as exc:  # pragma: no cover - defensive
                events.append(
                    {
                        "phase": "phase2_semantic",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "warning",
                        "message": f"External lineage agent failed: {exc}",
                    }
                )

        return events
