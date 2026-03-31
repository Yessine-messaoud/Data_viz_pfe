"""
LineageTracker: Tracks all transformations for audit and traceability
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

class LineageTracker:
    def __init__(self, lineage_agent=None):
        self.lineage_agent = lineage_agent

    def capture(self, tool_model: Dict) -> List[Dict]:
        datasets = tool_model.get("datasets", []) if isinstance(tool_model, dict) else []
        visuals = tool_model.get("visuals", []) if isinstance(tool_model, dict) else []

        event = {
            "phase": "phase4_transform",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "datasets_count": len(datasets) if isinstance(datasets, list) else 0,
            "visuals_count": len(visuals) if isinstance(visuals, list) else 0,
            "status": "ok" if isinstance(tool_model, dict) and "error" not in tool_model else "error",
        }
        events: List[Dict] = [event]

        if self.lineage_agent and hasattr(self.lineage_agent, "capture"):
            try:
                external = self.lineage_agent.capture(tool_model)
                if isinstance(external, list):
                    events.extend(external)
                elif isinstance(external, dict):
                    events.append(external)
            except Exception as exc:  # pragma: no cover - defensive
                events.append(
                    {
                        "phase": "phase4_transform",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "warning",
                        "message": f"External lineage agent failed: {exc}",
                    }
                )

        return events
