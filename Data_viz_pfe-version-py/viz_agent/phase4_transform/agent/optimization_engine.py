"""
OptimizationEngine: Applies tool-specific optimizations
"""
from typing import Any, Dict


class OptimizationEngine:
    def __init__(self, rules_config=None):
        self.rules_config = rules_config

    def _recommendations(self, tool_model: Dict, target_tool: str) -> list[str]:
        tool = target_tool.upper()
        datasets = tool_model.get("datasets", []) if isinstance(tool_model.get("datasets", []), list) else []
        visuals = tool_model.get("visuals", []) if isinstance(tool_model.get("visuals", []), list) else []
        recs: list[str] = []

        if tool == "POWERBI":
            if len(datasets) > 5:
                recs.append("Consider star-schema normalization and date table optimization.")
            if len(visuals) > 20:
                recs.append("Consider reducing visuals per page for render performance.")
        elif tool == "TABLEAU":
            recs.append("Prefer extract mode for large datasets.")
            if len(visuals) > 15:
                recs.append("Reduce dimensions in complex worksheets to improve responsiveness.")
        elif tool == "RDL":
            recs.append("Prefer server-side aggregation in dataset queries for heavy reports.")

        return recs

    def optimize(self, tool_model: Dict, target_tool: str, context: Dict) -> Dict:
        if not isinstance(tool_model, dict):
            return {"error": "tool_model must be a dictionary"}
        tool_model["optimization_hints"] = self._recommendations(tool_model, target_tool)
        return tool_model
