"""
VisualMappingEngine: Maps abstract visualizations to tool-specific visuals
"""
from typing import Any, Dict

from .rules import merge_rules


class VisualMappingEngine:
    def __init__(self, rules_config=None):
        self.rules = merge_rules(rules_config)

    def _tool_visual(self, business_type: str, target_tool: str) -> str:
        visual_map = self.rules.get("visual_mappings", {}).get(target_tool.upper(), {})
        return str(visual_map.get(business_type, visual_map.get("table", "table")))

    def transform(self, tool_model: Dict, target_tool: str, context: Dict) -> Dict:
        if not isinstance(tool_model, dict):
            return {"error": "tool_model must be a dictionary"}
        visuals = tool_model.get("visuals", [])
        if not isinstance(visuals, list):
            return tool_model

        mapped_visuals: list[dict] = []
        for visual in visuals:
            if not isinstance(visual, dict):
                continue
            business_type = str(visual.get("business_type", "table")).lower()
            mapped = dict(visual)
            mapped["tool_visual_type"] = self._tool_visual(business_type, target_tool)
            mapped_visuals.append(mapped)
        tool_model["visuals"] = mapped_visuals
        return tool_model
