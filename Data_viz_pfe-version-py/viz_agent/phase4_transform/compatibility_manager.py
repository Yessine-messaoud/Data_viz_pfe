from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .transformation_fixer import TransformationFixer
from .visual_compatibility import VisualCompatibility


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


class CompatibilityManager:
    def __init__(self, rules_config=None):
        self.rules_config = rules_config or {}
        self.visual_compatibility = VisualCompatibility()
        self.fixer = TransformationFixer()

    def _fallback_visual_type(self, visual_type: str, target_tool: str) -> str:
        tool = str(target_tool or "").upper()
        if tool == "LOOKER" and visual_type in {"treemap", "gantt"}:
            return "bar"
        return "table"

    def _normalize_datasets(self, tool_model: Dict[str, Any], logs: List[Dict[str, Any]]) -> None:
        datasets = tool_model.get("datasets", [])
        if not isinstance(datasets, list):
            tool_model["datasets"] = []
            logs.append({"step": "dataset_validation", "status": "error", "message": "datasets must be a list"})
            return

        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            name = str(dataset.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)

            fields = [field for field in dataset.get("fields", []) if isinstance(field, dict) and str(field.get("name") or field.get("source_field") or field.get("data_field") or "").strip()]
            dataset["fields"] = self._dedupe_fields(fields)
            if not dataset["fields"]:
                logs.append({"step": "dataset_validation", "status": "warning", "message": f"dataset {name} removed because it has no fields"})
                continue

            query = str(dataset.get("query") or "").strip()
            if query and "SELECT *" in query.upper() and dataset["fields"]:
                select_parts = []
                group_by = [str(value).strip() for value in dataset.get("group_by", []) if str(value).strip()]
                for field in dataset["fields"]:
                    field_name = str(field.get("name") or field.get("source_field") or field.get("data_field") or "").strip()
                    if not field_name:
                        continue
                    aggregation = str(field.get("aggregation") or "").strip().upper()
                    if aggregation:
                        select_parts.append(f"{aggregation}([{field_name}]) AS [{field_name}]")
                    else:
                        select_parts.append(f"[{field_name}]")
                if select_parts:
                    query = f"SELECT {', '.join(select_parts)} FROM {name}"
                    if group_by:
                        query += f" GROUP BY {', '.join(f'[{value}]' for value in group_by)}"
                    dataset["query"] = query
                    logs.append({"step": "dataset_validation", "status": "fixed", "message": f"dataset {name} query rebuilt without SELECT *"})

            normalized.append(dataset)

        tool_model["datasets"] = normalized

    def _dedupe_fields(self, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for field in fields:
            name = str(field.get("name") or field.get("source_field") or field.get("data_field") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(field)
        return deduped

    def resolve(self, tool_model: Dict, target_tool: str, context: Dict) -> Tuple[Dict, List[Dict]]:
        logs: List[Dict] = []
        if not isinstance(tool_model, dict):
            return {"error": "tool_model must be a dictionary"}, logs

        self._normalize_datasets(tool_model, logs)

        visuals = tool_model.get("visuals", [])
        if not isinstance(visuals, list):
            tool_model["visuals"] = []
            logs.append({"step": "visual_validation", "status": "error", "message": "visuals must be a list"})
            return tool_model, logs

        datasets_by_name = {str(dataset.get("name") or "").lower(): dataset for dataset in tool_model.get("datasets", []) if isinstance(dataset, dict)}
        semantic_model = tool_model.get("semantic_model") or context.get("semantic_model")

        normalized_visuals: list[dict[str, Any]] = []
        for visual in visuals:
            if not isinstance(visual, dict):
                continue
            visual_type = str(visual.get("business_type") or visual.get("type") or "table").lower()
            dataset_name = str(visual.get("dataset") or visual.get("dataset_name") or "").lower()
            dataset = datasets_by_name.get(dataset_name)

            compatibility = self.visual_compatibility.normalize_visual(visual, dataset, target_tool, semantic_model)
            corrected_visual = compatibility.visual

            if not compatibility.supported:
                fixer_result = self.fixer.fix(corrected_visual, dataset, semantic_model, target_tool)
                corrected_visual = fixer_result.visual
                dataset = fixer_result.dataset or dataset
                logs.extend(
                    {
                        "step": "correction",
                        "status": "applied",
                        "message": message,
                        "visual_id": corrected_visual.get("id", ""),
                    }
                    for message in fixer_result.corrections
                )
                if fixer_result.warnings:
                    logs.extend(
                        {
                            "step": "correction",
                            "status": "warning",
                            "message": warning,
                            "visual_id": corrected_visual.get("id", ""),
                        }
                        for warning in fixer_result.warnings
                    )

            if visual_type in {"treemap", "gantt"} and str(target_tool or "").upper() == "LOOKER":
                corrected_visual["business_type"] = self._fallback_visual_type(visual_type, target_tool)
                corrected_visual["tool_visual_type"] = corrected_visual["business_type"]

            corrected_visual.setdefault("business_type", str(corrected_visual.get("type") or "table").lower())
            if str(target_tool or "").upper() == "RDL":
                corrected_visual["tool_visual_type"] = corrected_visual.get("rdl_type") or compatibility.rdl_type

            normalized_visuals.append(corrected_visual)
            logs.extend(
                {
                    "step": "compatibility",
                    "status": "ok" if compatibility.supported else "fallback",
                    "message": message,
                    "visual_id": corrected_visual.get("id", ""),
                }
                for message in compatibility.warnings
            )

            if dataset is not None:
                datasets_by_name[str(dataset.get("name") or "").lower()] = dataset

        tool_model["visuals"] = normalized_visuals
        tool_model["datasets"] = list(datasets_by_name.values())
        tool_model["compatibility_notes"] = logs
        return tool_model, logs
