from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from viz_agent.models.abstract_spec import DataBinding, MeasureRef, SemanticModel, VisualSpec
from viz_agent.phase3_spec.visual_contracts import contract_for_visual_type, semantic_role_for_field, validate_visual_contract


@dataclass
class SpecCorrectionResult:
    visual_spec: VisualSpec
    corrected: bool
    issues: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)


class SpecCorrectionEngine:
    """Repair invalid visual specs by applying conservative fallbacks."""

    def correct(self, visual_spec: VisualSpec, semantic_model: SemanticModel) -> SpecCorrectionResult:
        issues: list[str] = []
        corrections: list[str] = []
        spec = visual_spec.model_copy(deep=True) if hasattr(visual_spec, "model_copy") else VisualSpec(**visual_spec.model_dump())

        contract = contract_for_visual_type(spec.type)
        if contract is None or spec.type == "chart" or spec.rdl_type == "chart":
            spec.type = "table"
            spec.rdl_type = "tablix"
            corrections.append("downgraded generic chart to table")

        # STEP 1: remove meaningless and duplicated encodings early.
        self._remove_duplicate_encodings(spec.data_binding, corrections)
        self._drop_empty_axes(spec.data_binding)

        # STEP 2: enforce semantic consistency for shared rules.
        self._enforce_general_semantics(spec.data_binding, semantic_model, corrections)

        validation = validate_visual_contract(spec, semantic_model)
        if not validation.is_valid:
            issues.extend(validation.issues)

        # STEP 3/4: normalize per visual contract.
        corrected_binding, binding_corrections = self._normalize_binding(spec.type, spec.data_binding, semantic_model)
        spec.data_binding = corrected_binding
        corrections.extend(binding_corrections)

        # STEP 5: normalize override to chart series contract.
        override = self._normalized_visual_override(spec.type)
        if spec.data_binding.visual_type_override != override:
            spec.data_binding.visual_type_override = override
            corrections.append(f"normalized visual_type_override to '{override}'")

        revalidation = validate_visual_contract(spec, semantic_model)
        if not revalidation.is_valid:
            issues.extend(revalidation.issues)

        return SpecCorrectionResult(
            visual_spec=spec,
            corrected=bool(corrections),
            issues=issues,
            corrections=corrections,
        )

    def _normalize_binding(self, visual_type: str, binding: DataBinding, semantic_model: SemanticModel) -> tuple[DataBinding, list[str]]:
        corrected = binding.model_copy(deep=True) if hasattr(binding, "model_copy") else DataBinding(**binding.model_dump())
        corrections: list[str] = []

        if visual_type in {"bar", "line", "scatter"}:
            if "size" in corrected.axes:
                corrected.axes.pop("size", None)
                corrections.append("Removed invalid size encoding (not allowed for bar/line/scatter)")
            self._ensure_axis(corrected, semantic_model, "x", "dimension", corrections)
            self._ensure_axis(corrected, semantic_model, "y", "measure", corrections)
            self._drop_axis_if_role_mismatch(corrected, semantic_model, "color", "dimension", corrections, "Removed invalid color encoding")
            self._drop_axis_if_role_mismatch(corrected, semantic_model, "detail", "dimension", corrections, "Removed invalid detail encoding")
        elif visual_type == "pie":
            self._ensure_axis(corrected, semantic_model, "x", "dimension", corrections)
            self._ensure_axis(corrected, semantic_model, "y", "measure", corrections)
            self._drop_axis_if_role_mismatch(corrected, semantic_model, "color", "dimension", corrections, "Removed invalid color encoding")
            self._drop_axis_if_role_mismatch(corrected, semantic_model, "detail", "dimension", corrections, "Removed invalid detail encoding")
        elif visual_type == "treemap":
            # Treemap contract: no x/y axes, group as dimension, size as measure, color optional dimension.
            if "x" in corrected.axes:
                corrected.axes.pop("x", None)
                corrections.append("Removed invalid x axis for treemap")
            if "y" in corrected.axes:
                corrected.axes.pop("y", None)
                corrections.append("Removed invalid y axis for treemap")

            has_group = bool(
                any(
                    value and semantic_role_for_field(semantic_model, value) == "dimension"
                    for value in corrected.group_by
                )
            )
            if not has_group:
                group_name = self._first_valid_dimension(corrected, semantic_model)
                if not group_name:
                    group_name = self._best_field(semantic_model, expected_role="dimension", preferred=[])
            else:
                group_name = ""

            if group_name:
                from viz_agent.models.abstract_spec import ColumnRef

                corrected.axes["group"] = ColumnRef(table="unknown", column=group_name)
                corrected.group_by = [group_name]
                corrections.append("Treemap missing group, inferred from dimension")

            self._ensure_axis(corrected, semantic_model, "size", "measure", corrections)
            self._drop_axis_if_role_mismatch(corrected, semantic_model, "color", "dimension", corrections, "Removed invalid color encoding")

            # Keep only first measure to avoid ambiguous treemap sizes.
            if len(corrected.measures) > 1:
                corrected.measures = corrected.measures[:1]
                corrections.append("Treemap had multiple measures, kept first measure only")
        elif visual_type == "kpi":
            self._ensure_axis(corrected, semantic_model, "y", "measure", corrections)
        elif visual_type == "map":
            self._ensure_axis(corrected, semantic_model, "x", "dimension", corrections)

        self._drop_empty_axes(corrected)
        return corrected, corrections

    def _enforce_general_semantics(self, binding: DataBinding, semantic_model: SemanticModel, corrections: list[str]) -> None:
        # measure cannot be used as detail
        detail_name = self._field_name(binding.axes.get("detail"))
        if detail_name and semantic_role_for_field(semantic_model, detail_name) == "measure":
            binding.axes.pop("detail", None)
            corrections.append("Invalid measure used in detail, removed")

        # dimension cannot be used as size
        size_name = self._field_name(binding.axes.get("size"))
        if size_name and semantic_role_for_field(semantic_model, size_name) == "dimension":
            binding.axes.pop("size", None)
            corrections.append("Removed invalid size encoding (dimension detected)")

    def _remove_duplicate_encodings(self, binding: DataBinding, corrections: list[str]) -> None:
        x_name = self._field_name(binding.axes.get("x"))
        color_name = self._field_name(binding.axes.get("color"))
        if x_name and color_name and x_name.lower() == color_name.lower():
            binding.axes.pop("color", None)
            corrections.append("Removed redundant color encoding")

    def _drop_empty_axes(self, binding: DataBinding) -> None:
        for axis_name in list(binding.axes.keys()):
            if not self._field_name(binding.axes.get(axis_name)).strip():
                binding.axes.pop(axis_name, None)

    def _drop_axis_if_role_mismatch(
        self,
        binding: DataBinding,
        semantic_model: SemanticModel,
        axis_name: str,
        expected_role: str,
        corrections: list[str],
        message: str,
    ) -> None:
        field_name = self._field_name(binding.axes.get(axis_name))
        if not field_name:
            return
        if semantic_role_for_field(semantic_model, field_name) != expected_role:
            binding.axes.pop(axis_name, None)
            corrections.append(message)

    def _first_valid_dimension(self, binding: DataBinding, semantic_model: SemanticModel) -> str:
        for axis_name in ("detail", "color", "x"):
            candidate = self._field_name(binding.axes.get(axis_name))
            if candidate and semantic_role_for_field(semantic_model, candidate) == "dimension":
                return candidate
        for value in binding.group_by:
            if value and semantic_role_for_field(semantic_model, value) == "dimension":
                return value
        return ""

    def _normalized_visual_override(self, visual_type: str) -> str:
        token = str(visual_type or "").strip().lower()
        mapping = {
            "bar": "Column",
            "line": "Line",
            "scatter": "Scatter",
            "pie": "Pie",
            "treemap": "TreeMap",
            "table": "",
            "kpi": "",
            "map": "",
            "gantt": "",
        }
        return mapping.get(token, "")

    def _ensure_axis(
        self,
        binding: DataBinding,
        semantic_model: SemanticModel,
        axis_name: str,
        expected_role: str,
        corrections: list[str],
    ) -> None:
        ref = binding.axes.get(axis_name)
        field_name = self._field_name(ref)
        if field_name and semantic_role_for_field(semantic_model, field_name) == expected_role:
            return

        replacement = self._best_field(semantic_model, expected_role=expected_role, preferred=[field_name, self._field_name(binding.axes.get("x")), self._field_name(binding.axes.get("y"))])
        if not replacement:
            binding.axes.pop(axis_name, None)
            corrections.append(f"cleared axis '{axis_name}' because no {expected_role} field was available")
            return

        if expected_role == "measure":
            binding.axes[axis_name] = MeasureRef(name=replacement)
            if all(existing.name != replacement for existing in binding.measures):
                binding.measures.append(MeasureRef(name=replacement))
        else:
            from viz_agent.models.abstract_spec import ColumnRef

            binding.axes[axis_name] = ColumnRef(table="unknown", column=replacement)
        corrections.append(f"set axis '{axis_name}' to '{replacement}'")

    def _best_field(self, semantic_model: SemanticModel, *, expected_role: str, preferred: list[str | None]) -> str:
        names = [str(name).strip() for name in preferred if str(name or "").strip()]
        for name in names:
            if semantic_role_for_field(semantic_model, name) == expected_role:
                return name

        if expected_role == "measure":
            for measure in getattr(semantic_model, "measures", []) or []:
                candidate = str(getattr(measure, "name", "") or getattr(measure, "tableau_expression", "") or "").strip()
                if candidate:
                    return candidate

        for entity in getattr(semantic_model, "entities", []) or []:
            columns = entity.get("columns", []) if isinstance(entity, dict) else getattr(entity, "columns", [])
            for column in columns or []:
                role = column.get("role", "unknown") if isinstance(column, dict) else getattr(column, "role", "unknown")
                if str(role or "unknown").lower() == expected_role:
                    name = column.get("name", "") if isinstance(column, dict) else getattr(column, "name", "")
                    candidate = str(name or "").strip()
                    if candidate:
                        return candidate

        # If dimension metadata is sparse, pick the first non-measure semantic column.
        if expected_role == "dimension":
            measure_names = {
                str(getattr(measure, "name", "") or "").strip().lower()
                for measure in getattr(semantic_model, "measures", []) or []
                if str(getattr(measure, "name", "") or "").strip()
            }
            for entity in getattr(semantic_model, "entities", []) or []:
                columns = entity.get("columns", []) if isinstance(entity, dict) else getattr(entity, "columns", [])
                for column in columns or []:
                    name = column.get("name", "") if isinstance(column, dict) else getattr(column, "name", "")
                    candidate = str(name or "").strip()
                    if candidate and candidate.lower() not in measure_names:
                        return candidate

        return names[0] if names else ""

    def _field_name(self, ref: Any) -> str:
        if hasattr(ref, "column"):
            return str(getattr(ref, "column", "") or "")
        if hasattr(ref, "name"):
            return str(getattr(ref, "name", "") or "")
        return str(ref or "")
