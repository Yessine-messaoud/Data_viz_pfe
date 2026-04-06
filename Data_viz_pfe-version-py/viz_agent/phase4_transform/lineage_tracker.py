from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


class LineageTracker:
    def __init__(self, lineage_agent=None):
        self.lineage_agent = lineage_agent

    def capture(self, tool_model: Dict) -> List[Dict]:
        datasets = tool_model.get("datasets", []) if isinstance(tool_model, dict) else []
        visuals = tool_model.get("visuals", []) if isinstance(tool_model, dict) else []

        field_to_dataset: list[dict[str, str]] = []
        dataset_to_visual: list[dict[str, str]] = []
        expression_to_rdl_field: list[dict[str, str]] = []

        for dataset in datasets if isinstance(datasets, list) else []:
            dataset_dict = _as_dict(dataset)
            dataset_name = str(dataset_dict.get("name") or "").strip()
            for field in dataset_dict.get("fields", []) or []:
                field_dict = _as_dict(field)
                field_name = str(field_dict.get("name") or field_dict.get("source_field") or field_dict.get("data_field") or "").strip()
                if field_name and dataset_name:
                    field_to_dataset.append({"field": field_name, "dataset": dataset_name})
                expression = str(field_dict.get("expression") or field_dict.get("rdl_expression") or field_dict.get("translated_expression") or "").strip()
                if expression and field_name:
                    expression_to_rdl_field.append({"expression": expression, "rdl_field": field_name})

        for visual in visuals if isinstance(visuals, list) else []:
            visual_dict = _as_dict(visual)
            dataset_name = str(visual_dict.get("dataset") or visual_dict.get("dataset_name") or "").strip()
            visual_id = str(visual_dict.get("id") or visual_dict.get("source_worksheet") or "").strip()
            if dataset_name and visual_id:
                dataset_to_visual.append({"dataset": dataset_name, "visual": visual_id})

        event = {
            "phase": "phase4_transform",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "datasets_count": len(datasets) if isinstance(datasets, list) else 0,
            "visuals_count": len(visuals) if isinstance(visuals, list) else 0,
            "status": "ok" if isinstance(tool_model, dict) and "error" not in tool_model else "error",
            "field_to_dataset": field_to_dataset,
            "dataset_to_visual": dataset_to_visual,
            "expression_to_rdl_field": expression_to_rdl_field,
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
