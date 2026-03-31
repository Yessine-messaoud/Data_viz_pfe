"""
LineageHook: Integrates with Lineage Agent for continuous lineage capture
"""
from datetime import datetime, timezone
from typing import Any, Dict

class LineageHook:
    def __init__(self, lineage_agent=None):
        self.lineage_agent = lineage_agent

    def capture(self, result: Dict) -> list:
        event = {
            "phase": "phase1_parser",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dashboards_count": len(result.get("dashboards", [])) if isinstance(result, dict) else 0,
            "visuals_count": len(result.get("visuals", [])) if isinstance(result, dict) else 0,
            "bindings_count": len(result.get("bindings", [])) if isinstance(result, dict) else 0,
            "status": "ok" if isinstance(result, dict) and "error" not in result else "error",
        }
        events = [event]

        if self.lineage_agent and hasattr(self.lineage_agent, "capture"):
            try:
                external = self.lineage_agent.capture(result)
                if isinstance(external, list):
                    events.extend(external)
                elif isinstance(external, dict):
                    events.append(external)
            except Exception as exc:  # pragma: no cover - defensive
                events.append(
                    {
                        "phase": "phase1_parser",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "warning",
                        "message": f"External lineage agent failed: {exc}",
                    }
                )

        return events
