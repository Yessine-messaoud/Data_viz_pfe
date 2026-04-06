from __future__ import annotations

from dataclasses import dataclass, field

from viz_agent.models.abstract_spec import ColumnRef, ConfidenceScore, DataBinding, MeasureRef, ParsedWorkbook, SemanticModel, VisualEncoding, VisualSpec
from viz_agent.phase1_parser.visual_type_mapper import resolve_visual_mapping
from viz_agent.phase3_spec.visual_contracts import binding_field_for_axis, contract_for_visual_type, semantic_role_for_field, set_binding_axis, validate_visual_contract


@dataclass
class VisualDecisionResult:
    final_visual_type: str
    rdl_type: str
    validated_data_binding: DataBinding
    adjusted_encoding: VisualEncoding
    confidence: float
    unstable: bool = False
    warnings: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)


class VisualDecisionEngine:
    """Resolve visual intent, enforce contracts, and return an RDL-ready binding."""

    def decide(
        self,
        *,
        worksheet_name: str,
        raw_mark_type: str,
        visual_encoding: VisualEncoding,
        confidence: ConfidenceScore,
        semantic_model: SemanticModel,
        workbook: ParsedWorkbook,
    ) -> VisualDecisionResult:
        mapping = resolve_visual_mapping(worksheet_name, raw_mark_type, visual_encoding)
        final_visual_type = mapping.logical_type
        rdl_type = mapping.rdl_type
        effective_confidence = float(confidence.overall or 0.0)
        if effective_confidence <= 0.0:
            effective_confidence = float(getattr(mapping, "confidence", 0.0) or 0.0)

        raw_mark_lower = str(raw_mark_type or "").strip().lower()
        worksheet_lower = worksheet_name.lower()
        if raw_mark_lower == "text" or "kpi" in worksheet_lower:
            final_visual_type = "kpi"
            rdl_type = "Textbox"

        adjusted_encoding = self._clone_encoding(visual_encoding)
        binding = self._build_binding(adjusted_encoding, semantic_model, workbook)

        warnings: list[str] = []
        corrections: list[str] = []
        unstable = False

        if mapping.warning:
            warnings.append(mapping.warning)

        if effective_confidence < 0.7:
            fallback_type, fallback_rdl = self._fallback_visual_type(adjusted_encoding, worksheet_name)
            if fallback_type != final_visual_type:
                final_visual_type = fallback_type
                rdl_type = fallback_rdl
                corrections.append(f"fallback visual selected: {fallback_type}")
            warnings.append(f"low confidence {effective_confidence:.2f}")

        if effective_confidence < 0.5:
            unstable = True

        binding, adjusted_encoding, decision_warnings, decision_corrections = self._enforce_contract(
            final_visual_type,
            binding,
            adjusted_encoding,
            semantic_model,
        )
        warnings.extend(decision_warnings)
        corrections.extend(decision_corrections)

        contract = contract_for_visual_type(final_visual_type)
        if contract is None:
            warnings.append(f"unknown visual contract '{final_visual_type}'")

        visual_spec = VisualSpec(
            id=worksheet_name,
            source_worksheet=worksheet_name,
            type=final_visual_type,
            rdl_type=rdl_type,
            title=worksheet_name,
            data_binding=binding,
        )
        validation = validate_visual_contract(visual_spec, semantic_model)
        if not validation.is_valid:
            warnings.extend(validation.issues)

        evolved_confidence = max(0.0, min(1.0, effective_confidence + (0.03 * len(corrections)) - (0.02 * len(warnings))))
        return VisualDecisionResult(
            final_visual_type=final_visual_type,
            rdl_type=rdl_type,
            validated_data_binding=binding,
            adjusted_encoding=adjusted_encoding,
            confidence=evolved_confidence,
            unstable=unstable,
            warnings=warnings,
            corrections=corrections,
        )

    def _build_binding(self, encoding: VisualEncoding, semantic_model: SemanticModel, workbook: ParsedWorkbook) -> DataBinding:
        binding = DataBinding()
        default_table = workbook.datasources[0].name if workbook.datasources else "unknown"

        for axis_name, field_name in {
            "x": encoding.x,
            "y": encoding.y,
            "color": encoding.color,
            "size": encoding.size,
            "detail": encoding.detail,
        }.items():
            if not field_name:
                continue
            self._set_axis(binding, axis_name, field_name, semantic_model, default_table)

        binding.group_by = [value for value in (encoding.x, encoding.color, encoding.detail) if value]
        binding.hierarchy = [value for value in (encoding.x, encoding.detail) if value]
        binding.aggregation = "SUM" if encoding.y or encoding.size else "NONE"
        return binding

    def _enforce_contract(
        self,
        visual_type: str,
        binding: DataBinding,
        encoding: VisualEncoding,
        semantic_model: SemanticModel,
    ) -> tuple[DataBinding, VisualEncoding, list[str], list[str]]:
        warnings: list[str] = []
        corrections: list[str] = []
        adjusted = self._clone_encoding(encoding)

        if visual_type in {"bar", "line", "scatter"}:
            self._ensure_axis_role(binding, semantic_model, adjusted, "x", "dimension", corrections, warnings)
            self._ensure_axis_role(binding, semantic_model, adjusted, "y", "measure", corrections, warnings)
        elif visual_type == "pie":
            self._ensure_axis_role(binding, semantic_model, adjusted, "x", "dimension", corrections, warnings)
            self._ensure_axis_role(binding, semantic_model, adjusted, "y", "measure", corrections, warnings)
        elif visual_type == "treemap":
            self._ensure_axis_role(binding, semantic_model, adjusted, "x", "dimension", corrections, warnings)
            self._ensure_axis_role(binding, semantic_model, adjusted, "y", "measure", corrections, warnings)
        elif visual_type == "kpi":
            self._ensure_axis_role(binding, semantic_model, adjusted, "y", "measure", corrections, warnings)
        elif visual_type == "map":
            self._ensure_axis_role(binding, semantic_model, adjusted, "x", "dimension", corrections, warnings)

        return binding, adjusted, warnings, corrections

    def _ensure_axis_role(
        self,
        binding: DataBinding,
        semantic_model: SemanticModel,
        encoding: VisualEncoding,
        axis_name: str,
        expected_role: str,
        corrections: list[str],
        warnings: list[str],
    ) -> None:
        field_name = binding_field_for_axis(binding, axis_name) or getattr(encoding, axis_name, None)
        if field_name and semantic_role_for_field(semantic_model, field_name) == expected_role:
            return

        preferred = [field_name, encoding.x, encoding.y, encoding.color, encoding.size, encoding.detail]
        replacement = self._best_field(semantic_model, expected_role=expected_role, preferred=preferred)
        if not replacement:
            warnings.append(f"unable to resolve {expected_role} for axis '{axis_name}'")
            return

        set_binding_axis(binding, axis_name, replacement, expected_role)
        setattr(encoding, axis_name, replacement)
        corrections.append(f"set axis '{axis_name}' to '{replacement}'")

    def _fallback_visual_type(self, encoding: VisualEncoding, worksheet_name: str) -> tuple[str, str]:
        worksheet_lower = worksheet_name.lower()
        if any(token in worksheet_lower for token in ("map", "geo", "country", "region")):
            return "map", "Map"
        if encoding.size and (encoding.color or encoding.detail):
            return "treemap", "TreeMap"
        if encoding.x and encoding.y:
            return "bar", "ColumnChart"
        if encoding.y and not encoding.x:
            return "kpi", "Textbox"
        return "table", "Tablix"

    def _clone_encoding(self, encoding: VisualEncoding) -> VisualEncoding:
        return encoding.model_copy(deep=True) if hasattr(encoding, "model_copy") else VisualEncoding(**encoding.model_dump())

    def _set_axis(self, binding: DataBinding, axis_name: str, field_name: str, semantic_model: SemanticModel, default_table: str) -> None:
        role = semantic_role_for_field(semantic_model, field_name)
        if role == "measure":
            binding.axes[axis_name] = MeasureRef(name=field_name)
            if all(existing.name != field_name for existing in binding.measures):
                binding.measures.append(MeasureRef(name=field_name))
        else:
            binding.axes[axis_name] = ColumnRef(table=default_table, column=field_name)

    def _best_field(self, semantic_model: SemanticModel, *, expected_role: str, preferred: list[str | None]) -> str:
        candidates = [str(value).strip() for value in preferred if str(value or "").strip()]
        for candidate in candidates:
            if semantic_role_for_field(semantic_model, candidate) == expected_role:
                return candidate

        if expected_role == "measure":
            for measure in getattr(semantic_model, "measures", []) or []:
                candidate = str(getattr(measure, "name", "") or getattr(measure, "tableau_expression", "") or "").strip()
                if candidate:
                    return candidate

        for entity in getattr(semantic_model, "entities", []) or []:
            for column in getattr(entity, "columns", []) or []:
                if str(getattr(column, "role", "unknown") or "unknown").lower() == expected_role:
                    candidate = str(getattr(column, "name", "") or "").strip()
                    if candidate:
                        return candidate

        return candidates[0] if candidates else ""
