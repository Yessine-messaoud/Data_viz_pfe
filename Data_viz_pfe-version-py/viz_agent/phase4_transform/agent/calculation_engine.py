"""
CalculationEngine: Translates abstract calculations to tool-specific expressions
"""
from typing import Any, Dict


class CalculationEngine:
    def __init__(self, rules_config=None):
        self.rules_config = rules_config

    def _translate_expression(self, expression: str, target_tool: str) -> str:
        text = str(expression or "").strip()
        if not text:
            return text
        tool = target_tool.upper()
        if tool == "TABLEAU":
            text = text.replace("COUNT_DISTINCT(", "COUNTD(")
            text = text.replace("AVG(", "AVG(")
            text = text.replace("SUM(", "SUM(")
        elif tool == "POWERBI":
            text = text.replace("COUNT_DISTINCT(", "DISTINCTCOUNT(")
        return text

    def transform(self, tool_model: Dict, target_tool: str, context: Dict) -> Dict:
        if not isinstance(tool_model, dict):
            return {"error": "tool_model must be a dictionary"}
        measures = tool_model.get("measures", [])
        if not isinstance(measures, list):
            return tool_model

        translated = []
        for measure in measures:
            if not isinstance(measure, dict):
                continue
            cloned = dict(measure)
            cloned["translated_expression"] = self._translate_expression(
                str(measure.get("expression", "")),
                target_tool,
            )
            translated.append(cloned)
        tool_model["measures"] = translated
        return tool_model
