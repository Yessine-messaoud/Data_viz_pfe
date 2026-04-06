from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from viz_agent.models.abstract_spec import ColumnRef, DataBinding, MeasureRef, SemanticModel, VisualSpec


@dataclass(frozen=True)
class VisualContract:
    name: str
    required: dict[str, str]
    optional: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    preferred_axes: tuple[str, ...] = ("x", "y", "color", "size", "detail")


@dataclass
class ValidationResult:
    is_valid: bool
    contract_name: str
    issues: list[str] = field(default_factory=list)
    resolved_fields: dict[str, str] = field(default_factory=dict)


BAR_CONTRACT = VisualContract(
    name="bar",
    required={"x": "dimension", "y": "measure"},
    optional=("color", "detail"),
)
LINE_CONTRACT = VisualContract(
    name="line",
    required={"x": "dimension", "y": "measure"},
    optional=("color", "detail"),
)
PIE_CONTRACT = VisualContract(
    name="pie",
    required={"category": "dimension", "value": "measure"},
    optional=("color", "detail"),
)
TREEMAP_CONTRACT = VisualContract(
    name="treemap",
    required={"group": "dimension", "size": "measure"},
    optional=("color", "detail"),
)
SCATTER_CONTRACT = VisualContract(
    name="scatter",
    required={"x": "dimension", "y": "measure"},
    optional=("color", "size", "detail"),
)
KPI_CONTRACT = VisualContract(
    name="kpi",
    required={"value": "measure"},
    optional=("detail",),
)
TABLE_CONTRACT = VisualContract(name="table", required={}, optional=("x", "y", "color", "size", "detail"))
MAP_CONTRACT = VisualContract(name="map", required={"location": "dimension"}, optional=("value", "color", "detail"))
GANTT_CONTRACT = VisualContract(name="gantt", required={"task": "dimension", "duration": "measure"}, optional=("detail",))

VISUAL_CONTRACTS: dict[str, VisualContract] = {
    "bar": BAR_CONTRACT,
    "line": LINE_CONTRACT,
    "pie": PIE_CONTRACT,
    "treemap": TREEMAP_CONTRACT,
    "scatter": SCATTER_CONTRACT,
    "kpi": KPI_CONTRACT,
    "table": TABLE_CONTRACT,
    "tablix": TABLE_CONTRACT,
    "map": MAP_CONTRACT,
    "gantt": GANTT_CONTRACT,
}

LOGICAL_FROM_RDL: dict[str, str] = {
    "columnchart": "bar",
    "linechart": "line",
    "piechart": "pie",
    "treemap": "treemap",
    "scatterchart": "scatter",
    "textbox": "kpi",
    "map": "map",
    "tablix": "table",
}


def normalize_visual_type(value: str) -> str:
    token = str(value or "").strip().lower()
    return LOGICAL_FROM_RDL.get(token, token)


def contract_for_visual_type(value: str) -> VisualContract | None:
    return VISUAL_CONTRACTS.get(normalize_visual_type(value))


def semantic_role_for_field(semantic_model: SemanticModel, field_name: str) -> str:
    wanted = str(field_name or "").strip().lower()
    if not wanted:
        return "unknown"

    for entity in getattr(semantic_model, "entities", []) or []:
        for column in getattr(entity, "columns", []) or []:
            column_name = str(getattr(column, "name", "") or "").strip().lower()
            if column_name == wanted:
                return str(getattr(column, "role", "unknown") or "unknown").lower()

    for measure in getattr(semantic_model, "measures", []) or []:
        measure_name = str(getattr(measure, "name", "") or "").strip().lower()
        source_expr = str(getattr(measure, "tableau_expression", "") or "").strip().lower()
        if measure_name == wanted or source_expr == wanted:
            return "measure"

    for dimension in getattr(semantic_model, "dimensions", []) or []:
        dim_name = str(getattr(dimension, "name", dimension) or "").strip().lower()
        if dim_name == wanted:
            return "dimension"

    if wanted.endswith("_id") or wanted.endswith("id"):
        return "dimension"
    if any(token in wanted for token in ("amount", "sales", "profit", "revenue", "cost", "qty", "quantity", "total", "count", "score", "value", "size", "duration")):
        return "measure"
    return "dimension"


def binding_field_for_axis(binding: DataBinding, axis_name: str) -> str:
    axis_name = str(axis_name or "").strip().lower()
    if axis_name in {"x", "y", "color", "size", "detail"}:
        ref = binding.axes.get(axis_name)
        if hasattr(ref, "column"):
            return str(getattr(ref, "column", "") or "")
        if hasattr(ref, "name"):
            return str(getattr(ref, "name", "") or "")
        return ""

    if axis_name in {"category", "group", "location", "task"}:
        for candidate in ("x", "color", "detail"):
            value = binding_field_for_axis(binding, candidate)
            if value:
                return value
    if axis_name in {"value", "duration"}:
        for candidate in ("y", "size"):
            value = binding_field_for_axis(binding, candidate)
            if value:
                return value
    return ""


def set_binding_axis(binding: DataBinding, axis_name: str, field_name: str, role: str) -> None:
    axis_name = str(axis_name or "").strip().lower()
    if not field_name:
        binding.axes.pop(axis_name, None)
        return

    if role == "measure":
        binding.axes[axis_name] = MeasureRef(name=field_name)
        if all(existing.name != field_name for existing in binding.measures):
            binding.measures.append(MeasureRef(name=field_name))
    else:
        binding.axes[axis_name] = ColumnRef(table="unknown", column=field_name)


def _binding_to_field_name(binding: DataBinding, axis_name: str) -> str:
    ref = binding.axes.get(axis_name)
    if hasattr(ref, "column"):
        return str(getattr(ref, "column", "") or "")
    if hasattr(ref, "name"):
        return str(getattr(ref, "name", "") or "")
    return str(ref or "")


def _candidate_fields(binding: DataBinding, axis_name: str) -> list[str]:
    fields: list[str] = []
    raw = _binding_to_field_name(binding, axis_name)
    if raw:
        fields.append(raw)
    for value in binding.group_by:
        if value and value not in fields:
            fields.append(value)
    for value in binding.hierarchy:
        if value and value not in fields:
            fields.append(value)
    for ref in binding.measures:
        name = str(getattr(ref, "name", "") or "").strip()
        if name and name not in fields:
            fields.append(name)
    return fields


def _validate_axis(binding: DataBinding, semantic_model: SemanticModel, axis_name: str, expected_role: str, issues: list[str], resolved: dict[str, str]) -> str:
    candidates = _candidate_fields(binding, axis_name)
    if not candidates:
        issues.append(f"missing axis '{axis_name}' for expected role '{expected_role}'")
        return ""

    for candidate in candidates:
        role = semantic_role_for_field(semantic_model, candidate)
        if role == expected_role:
            resolved[axis_name] = candidate
            return candidate

    issues.append(
        f"axis '{axis_name}' candidates {candidates} do not match expected role '{expected_role}'"
    )
    resolved[axis_name] = candidates[0]
    return candidates[0]


def validate_visual_contract(visual_spec: VisualSpec, semantic_model: SemanticModel) -> ValidationResult:
    contract = contract_for_visual_type(getattr(visual_spec, "type", ""))
    if contract is None:
        return ValidationResult(is_valid=False, contract_name=str(getattr(visual_spec, "type", "unknown")), issues=["unknown visual type"], resolved_fields={})

    binding = visual_spec.data_binding
    issues: list[str] = []
    resolved: dict[str, str] = {}

    if contract.name in {"bar", "line", "scatter"}:
        _validate_axis(binding, semantic_model, "x", "dimension", issues, resolved)
        _validate_axis(binding, semantic_model, "y", "measure", issues, resolved)
    elif contract.name == "pie":
        _validate_axis(binding, semantic_model, "category", "dimension", issues, resolved)
        _validate_axis(binding, semantic_model, "value", "measure", issues, resolved)
    elif contract.name == "treemap":
        _validate_axis(binding, semantic_model, "group", "dimension", issues, resolved)
        _validate_axis(binding, semantic_model, "size", "measure", issues, resolved)
    elif contract.name == "kpi":
        _validate_axis(binding, semantic_model, "value", "measure", issues, resolved)
    elif contract.name == "map":
        _validate_axis(binding, semantic_model, "location", "dimension", issues, resolved)
    elif contract.name == "gantt":
        _validate_axis(binding, semantic_model, "task", "dimension", issues, resolved)
        _validate_axis(binding, semantic_model, "duration", "measure", issues, resolved)

    generic_chart = str(getattr(visual_spec, "type", "") or "").strip().lower() == "chart" or str(getattr(visual_spec, "rdl_type", "") or "").strip().lower() == "chart"
    if generic_chart:
        issues.append("generic chart type is not allowed")

    return ValidationResult(
        is_valid=len(issues) == 0,
        contract_name=contract.name,
        issues=issues,
        resolved_fields=resolved,
    )
