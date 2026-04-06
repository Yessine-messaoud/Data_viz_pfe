from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HeuristicFixResult:
    applied: bool
    fix_name: str = ""
    notes: list[str] = field(default_factory=list)


class HeuristicFallbackEngine:
    """Applies lightweight heuristic repair hints before another retry."""

    def apply(
        self,
        phase_name: str,
        state: dict[str, Any],
        errors: list[str],
        *,
        attempt: int,
    ) -> HeuristicFixResult:
        context = state.setdefault("context", {}) if isinstance(state, dict) else {}
        hints = context.setdefault("heuristic_fixes", {}) if isinstance(context, dict) else {}
        phase_hints: dict[str, Any] = hints.setdefault(phase_name, {}) if isinstance(hints, dict) else {}

        if phase_name == "parsing":
            phase_hints["infer_dashboards_from_visuals"] = True
            phase_hints["confidence_boost_on_repaired_bindings"] = True
            return HeuristicFixResult(
                applied=True,
                fix_name="infer_dashboards_from_visuals",
                notes=[f"attempt={attempt}", "Infers minimal dashboards from parsed visuals when missing."],
            )

        if phase_name == "semantic_reasoning":
            phase_hints["infer_default_measure_from_numeric_candidates"] = True
            return HeuristicFixResult(
                applied=True,
                fix_name="infer_default_measure_from_numeric_candidates",
                notes=[f"attempt={attempt}", "Promotes numeric-like fields to candidate measures if measure set is empty."],
            )

        if phase_name == "specification":
            phase_hints["normalize_generic_chart_type"] = True
            phase_hints["inject_safe_axis_defaults"] = True
            return HeuristicFixResult(
                applied=True,
                fix_name="normalize_generic_chart_type",
                notes=[f"attempt={attempt}", "Replaces generic chart type with deterministic safe chart type."],
            )

        if phase_name == "export":
            phase_hints["accept_warnings_only_validation"] = True
            return HeuristicFixResult(
                applied=True,
                fix_name="accept_warnings_only_validation",
                notes=[f"attempt={attempt}", "Allows pass when payload is valid and only warnings remain."],
            )

        if errors:
            return HeuristicFixResult(applied=False, fix_name="no_known_heuristic", notes=[f"attempt={attempt}"])
        return HeuristicFixResult(applied=False, fix_name="no_op", notes=[])
