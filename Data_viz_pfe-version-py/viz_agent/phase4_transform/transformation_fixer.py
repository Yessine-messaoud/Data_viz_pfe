from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .visual_compatibility import VisualCompatibility


@dataclass
class TransformationFixResult:
    visual: dict[str, Any]
    dataset: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    confidence: float = 1.0


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


def _semantic_fields(semantic_model: Any, role: str) -> list[str]:
    fields: list[str] = []
    model_dict = _as_dict(semantic_model)
    for entity in model_dict.get("entities", []) or getattr(semantic_model, "entities", []) or []:
        entity_dict = _as_dict(entity)
        for column in entity_dict.get("columns", []) or getattr(entity, "columns", []) or []:
            column_dict = _as_dict(column)
            column_name = str(column_dict.get("name") or getattr(column, "name", "") or "").strip()
            column_role = str(column_dict.get("role") or getattr(column, "role", "unknown") or "unknown").lower()
            if column_name and column_role == role:
                fields.append(column_name)
    return fields


class TransformationFixer:
    def __init__(self) -> None:
        self.visual_compatibility = VisualCompatibility()

    def fix(self, visual: dict[str, Any], dataset: dict[str, Any] | None, semantic_model: Any, target_tool: str) -> TransformationFixResult:
        cloned_visual = dict(_as_dict(visual))
        cloned_dataset = dict(dataset) if isinstance(dataset, dict) else None
        warnings: list[str] = []
        corrections: list[str] = []
        confidence = float(cloned_visual.get("confidence", 1.0) or 1.0)

        binding = _as_dict(cloned_visual.get("data_binding"))
        axes = _as_dict(binding.get("axes"))
        visual_type = _normalize_text(cloned_visual.get("type") or cloned_visual.get("business_type") or "table")

        if cloned_dataset is not None:
            dataset_fields = {_normalize_text(str(field.get("name") or field.get("source_field") or field.get("data_field") or "")) for field in cloned_dataset.get("fields", []) if isinstance(field, dict)}
        else:
            dataset_fields = set()

        if visual_type == "treemap":
            if not self._axis_field(axes, "group"):
                inferred = self._infer_dimension(semantic_model, dataset_fields)
                if inferred:
                    axes["group"] = {"table": cloned_dataset.get("source_name", ""), "column": inferred} if cloned_dataset else {"column": inferred}
                    corrections.append(f"inferred treemap group '{inferred}'")
                    warnings.append(f"{cloned_visual.get('id', 'visual')}: Treemap missing group, inferred from dimension")
                    confidence -= 0.15
            if not self._axis_field(axes, "size"):
                inferred = self._infer_measure(semantic_model, dataset_fields)
                if inferred:
                    axes["size"] = {"table": cloned_dataset.get("source_name", ""), "column": inferred} if cloned_dataset else {"column": inferred}
                    corrections.append(f"inferred treemap size '{inferred}'")
                    warnings.append(f"{cloned_visual.get('id', 'visual')}: Treemap missing size, inferred from measure")
                    confidence -= 0.15

        if visual_type in {"bar", "line", "scatter", "pie", "map"} and not self._axis_field(axes, "y"):
            inferred_measure = self._infer_measure(semantic_model, dataset_fields)
            if inferred_measure:
                axes["y"] = {"table": cloned_dataset.get("source_name", ""), "column": inferred_measure} if cloned_dataset else {"column": inferred_measure}
                corrections.append(f"inferred missing measure '{inferred_measure}'")
                warnings.append(f"{cloned_visual.get('id', 'visual')}: missing measure inferred from semantic model")
                confidence -= 0.1

        if self._axis_field(axes, "size") and self._role_for_field(semantic_model, self._axis_field(axes, "size")) == "dimension":
            axes.pop("size", None)
            warnings.append(f"{cloned_visual.get('id', 'visual')}: Removed invalid size encoding (dimension detected)")
            corrections.append("removed dimension size encoding")
            confidence -= 0.1

        if self._axis_field(axes, "detail") and self._role_for_field(semantic_model, self._axis_field(axes, "detail")) == "measure":
            axes.pop("detail", None)
            warnings.append(f"{cloned_visual.get('id', 'visual')}: Invalid measure used in detail, removed")
            corrections.append("removed measure detail encoding")
            confidence -= 0.1

        cloned_visual["data_binding"] = binding
        compatibility = self.visual_compatibility.normalize_visual(cloned_visual, cloned_dataset, target_tool, semantic_model)
        cloned_visual = compatibility.visual
        warnings.extend(compatibility.warnings)
        if compatibility.errors:
            warnings.extend(compatibility.errors)
            confidence -= 0.2

        cloned_visual["confidence"] = max(0.0, min(1.0, confidence))
        if cloned_dataset is not None and not cloned_dataset.get("fields"):
            warnings.append(f"{cloned_visual.get('id', 'visual')}: empty dataset after fixes")

        return TransformationFixResult(
            visual=cloned_visual,
            dataset=cloned_dataset,
            warnings=warnings,
            corrections=corrections,
            confidence=cloned_visual["confidence"],
        )

    def _axis_field(self, axes: dict[str, Any], axis_name: str) -> str:
        ref = axes.get(axis_name)
        if isinstance(ref, dict):
            return str(ref.get("column") or ref.get("name") or "").strip()
        return str(getattr(ref, "column", "") or getattr(ref, "name", "") or "").strip()

    def _role_for_field(self, semantic_model: Any, field_name: str) -> str:
        if not field_name:
            return "unknown"
        normalized = _normalize_text(field_name)
        model_dict = _as_dict(semantic_model)
        for entity in model_dict.get("entities", []) or getattr(semantic_model, "entities", []) or []:
            entity_dict = _as_dict(entity)
            for column in entity_dict.get("columns", []) or getattr(entity, "columns", []) or []:
                column_dict = _as_dict(column)
                column_name = str(column_dict.get("name") or getattr(column, "name", "") or "").strip()
                column_role = str(column_dict.get("role") or getattr(column, "role", "unknown") or "unknown").lower()
                if _normalize_text(column_name) == normalized:
                    return column_role
        return "unknown"

    def _infer_dimension(self, semantic_model: Any, dataset_fields: set[str]) -> str:
        for field in _semantic_fields(semantic_model, "dimension"):
            if _normalize_text(field) in dataset_fields or not dataset_fields:
                return field
        for field in dataset_fields:
            return field
        return ""

    def _infer_measure(self, semantic_model: Any, dataset_fields: set[str]) -> str:
        for field in _semantic_fields(semantic_model, "measure"):
            if _normalize_text(field) in dataset_fields or not dataset_fields:
                return field
        return ""
