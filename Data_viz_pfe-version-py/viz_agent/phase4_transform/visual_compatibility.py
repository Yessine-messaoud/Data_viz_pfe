from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RDL_VISUAL_MAP = {
    "bar": "ColumnChart",
    "line": "LineChart",
    "pie": "PieChart",
    "treemap": "TreeMap",
    "scatter": "ScatterChart",
    "table": "Tablix",
    "kpi": "Textbox",
    "map": "Map",
    "gantt": "Tablix",
}


SUPPORTED_VISUALS = set(RDL_VISUAL_MAP)


@dataclass
class VisualCompatibilityResult:
    visual: dict[str, Any]
    supported: bool
    rdl_type: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    removed_axes: list[str] = field(default_factory=list)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _field_name(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("column") or ref.get("name") or "").strip()
    return str(getattr(ref, "column", "") or getattr(ref, "name", "") or ref or "").strip()


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


class VisualCompatibility:
    def normalize_visual(self, visual: dict[str, Any], dataset: dict[str, Any] | None, target_tool: str, semantic_model: Any | None = None) -> VisualCompatibilityResult:
        cloned = dict(_as_dict(visual))
        visual_type = _normalize_text(cloned.get("type") or cloned.get("business_type") or cloned.get("tool_visual_type") or "table")
        target = _normalize_text(target_tool or "RDL").upper()
        dataset_fields = self._dataset_fields(dataset)
        warnings: list[str] = []
        errors: list[str] = []
        removed_axes: list[str] = []

        if target == "LOOKER" and visual_type in {"treemap", "gantt"}:
            visual_type = "bar"
            warnings.append(f"{cloned.get('id', 'visual')}: unsupported visual replaced with bar for LOOKER")

        if visual_type not in SUPPORTED_VISUALS:
            warnings.append(f"{cloned.get('id', 'visual')}: unsupported visual '{visual_type}', fallback to tablix")
            visual_type = "table"

        binding = _as_dict(cloned.get("data_binding"))
        axes = _as_dict(binding.get("axes"))

        if visual_type in {"bar", "line", "scatter"}:
            for axis_name in ("size",):
                if axis_name in axes:
                    axes.pop(axis_name, None)
                    removed_axes.append(axis_name)
                    warnings.append(f"{cloned.get('id', 'visual')}: removed unsupported {axis_name} axis")
            self._ensure_required_axes(cloned, axes, ("x", "y"), dataset_fields, warnings, errors)
            self._validate_axis_roles(cloned, axes, dataset_fields, {"x": "dimension", "y": "measure", "color": "dimension", "detail": "dimension"}, warnings)
        elif visual_type == "pie":
            self._ensure_required_axes(cloned, axes, ("x", "y"), dataset_fields, warnings, errors)
            self._validate_axis_roles(cloned, axes, dataset_fields, {"x": "dimension", "y": "measure", "color": "dimension", "detail": "dimension"}, warnings)
        elif visual_type == "treemap":
            for axis_name in ("x", "y"):
                if axis_name in axes:
                    axes.pop(axis_name, None)
                    removed_axes.append(axis_name)
                    warnings.append(f"{cloned.get('id', 'visual')}: removed unsupported {axis_name} axis for treemap")
            group_name = _field_name(axes.get("group")) or _field_name(axes.get("detail")) or _field_name(axes.get("color"))
            size_name = _field_name(axes.get("size"))
            if not group_name or not self._exists_in_dataset(group_name, dataset_fields):
                errors.append(f"{cloned.get('id', 'visual')}: treemap requires a dimension group")
            if not size_name or not self._exists_in_dataset(size_name, dataset_fields):
                errors.append(f"{cloned.get('id', 'visual')}: treemap requires a measure size")
            self._validate_axis_roles(cloned, axes, dataset_fields, {"group": "dimension", "size": "measure", "color": "dimension"}, warnings)
        elif visual_type == "kpi":
            self._ensure_required_axes(cloned, axes, ("y",), dataset_fields, warnings, errors)
            self._validate_axis_roles(cloned, axes, dataset_fields, {"y": "measure"}, warnings)
        elif visual_type == "map":
            self._ensure_required_axes(cloned, axes, ("x",), dataset_fields, warnings, errors)
            self._validate_axis_roles(cloned, axes, dataset_fields, {"x": "dimension", "color": "dimension"}, warnings)

        rdl_type = RDL_VISUAL_MAP.get(visual_type, "Tablix")
        cloned["type"] = visual_type
        cloned["rdl_type"] = rdl_type
        cloned["business_type"] = visual_type
        cloned["tool_visual_type"] = rdl_type if target == "RDL" else visual_type
        cloned["data_binding"] = binding

        supported = not errors
        if visual_type == "treemap" and target == "RDL":
            warnings.append(f"{cloned.get('id', 'visual')}: treemap support is limited, validated structurally")

        return VisualCompatibilityResult(
            visual=cloned,
            supported=supported,
            rdl_type=rdl_type,
            warnings=warnings,
            errors=errors,
            removed_axes=removed_axes,
        )

    def _dataset_fields(self, dataset: dict[str, Any] | None) -> set[str]:
        if not dataset:
            return set()
        fields = dataset.get("fields", []) if isinstance(dataset, dict) else []
        names: set[str] = set()
        for field in fields or []:
            field_dict = _as_dict(field)
            name = str(field_dict.get("name") or field_dict.get("source_field") or field_dict.get("data_field") or "").strip()
            if name:
                names.add(_normalize_text(name))
        return names

    def _exists_in_dataset(self, field_name: str, dataset_fields: set[str]) -> bool:
        return _normalize_text(field_name) in dataset_fields

    def _ensure_required_axes(
        self,
        visual: dict[str, Any],
        axes: dict[str, Any],
        required_axes: tuple[str, ...],
        dataset_fields: set[str],
        warnings: list[str],
        errors: list[str],
    ) -> None:
        for axis_name in required_axes:
            field_name = _field_name(axes.get(axis_name))
            if not field_name:
                errors.append(f"{visual.get('id', 'visual')}: missing required axis '{axis_name}'")
                continue
            if not self._exists_in_dataset(field_name, dataset_fields):
                warnings.append(f"{visual.get('id', 'visual')}: axis '{axis_name}' not found in dataset")

    def _validate_axis_roles(
        self,
        visual: dict[str, Any],
        axes: dict[str, Any],
        dataset_fields: set[str],
        expected_roles: dict[str, str],
        warnings: list[str],
    ) -> None:
        for axis_name, expected_role in expected_roles.items():
            ref = axes.get(axis_name)
            field_name = _field_name(ref)
            if not field_name:
                continue
            if not self._exists_in_dataset(field_name, dataset_fields):
                warnings.append(f"{visual.get('id', 'visual')}: field '{field_name}' missing from dataset")
            if expected_role == "measure" and axis_name in {"color", "detail", "group"}:
                warnings.append(f"{visual.get('id', 'visual')}: '{axis_name}' should not use a measure")
            if expected_role == "dimension" and axis_name in {"size"}:
                warnings.append(f"{visual.get('id', 'visual')}: dimension field cannot be used in size")
