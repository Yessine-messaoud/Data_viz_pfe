from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeterministicFixResult:
    applied: bool
    fix_name: str = ""
    notes: list[str] = field(default_factory=list)


class DeterministicFallbackEngine:
    """Applies deterministic repair hints before retries."""

    def apply(self, phase_name: str, state: dict[str, Any], errors: list[str]) -> DeterministicFixResult:
        context = state.setdefault("context", {}) if isinstance(state, dict) else {}
        hints = context.setdefault("deterministic_fixes", {}) if isinstance(context, dict) else {}

        phase_hints: dict[str, Any] = hints.setdefault(phase_name, {}) if isinstance(hints, dict) else {}
        joined = " ".join(str(e) for e in errors).lower()

        if phase_name == "parsing":
            phase_hints["ensure_worksheets_from_visuals"] = True
            return DeterministicFixResult(applied=True, fix_name="ensure_worksheets_from_visuals", notes=["Synthesizes worksheets from visual source_worksheet."])

        if phase_name == "semantic_reasoning":
            phase_hints["drop_aggregated_dimension_measures"] = True
            return DeterministicFixResult(applied=True, fix_name="drop_aggregated_dimension_measures", notes=["Removes SUM/AVG over dimensions."])

        if phase_name == "specification":
            phase_hints["inject_chart_y_from_measures"] = True
            phase_hints["remove_dimension_from_size"] = True
            return DeterministicFixResult(applied=True, fix_name="inject_chart_y_from_measures", notes=["Injects missing chart Y from measures and sanitizes size axis."])

        if phase_name == "export":
            phase_hints["repair_export_validation_flags"] = True
            return DeterministicFixResult(applied=True, fix_name="repair_export_validation_flags", notes=["Repairs validation flags when payload exists."])

        # Fallback no-op for unknown phase.
        if "validation gate failed" in joined:
            return DeterministicFixResult(applied=False, fix_name="no_known_fix", notes=["No deterministic fix available for this phase."])
        return DeterministicFixResult(applied=False, fix_name="no_op", notes=[])
