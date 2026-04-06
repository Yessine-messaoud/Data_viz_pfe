from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class GateCheckResult:
    passed: bool
    issues: list[str] = field(default_factory=list)


class ValidationGates:
    """Deterministic validation gates that secure phase-to-phase transitions."""

    AGG_FUNCS = ("sum", "avg", "average", "count", "min", "max")

    def validate(self, phase_name: str, output: dict[str, Any]) -> GateCheckResult:
        if phase_name == "parsing":
            return self._gate_phase1(output)
        if phase_name == "semantic_reasoning":
            return self._gate_phase2(output)
        if phase_name == "specification":
            return self._gate_phase3(output)
        if phase_name == "export":
            return self._gate_phase5(output)
        if phase_name == "runtime_validation":
            return self._gate_runtime_validation(output)
        return GateCheckResult(passed=True, issues=[])

    def _gate_phase1(self, output: dict[str, Any]) -> GateCheckResult:
        parsed = self._as_dict(output.get("parsed_structure"))
        worksheets = parsed.get("worksheets") if isinstance(parsed.get("worksheets"), list) else []
        visuals = parsed.get("visuals") if isinstance(parsed.get("visuals"), list) else []

        has_worksheets = len(worksheets) > 0
        has_visual_linked_worksheet = any(bool(self._as_dict(v).get("source_worksheet")) for v in visuals)

        if has_worksheets or has_visual_linked_worksheet:
            return GateCheckResult(passed=True)
        return GateCheckResult(
            passed=False,
            issues=["Phase1 gate failed: no valid worksheets detected in parsed output."],
        )

    def _gate_phase2(self, output: dict[str, Any]) -> GateCheckResult:
        graph = self._as_dict(output.get("semantic_graph"))
        issues: list[str] = []

        dimensions = self._collect_dimension_names(graph)
        measure_expressions = self._collect_measure_expressions(graph)

        for expr in measure_expressions:
            expr_low = expr.lower()
            for dim in dimensions:
                if self._is_aggregating_dimension(expr_low, dim.lower()):
                    issues.append(f"Phase2 gate failed: aggregated dimension detected in measure expression '{expr}'.")
                    break

        if issues:
            return GateCheckResult(passed=False, issues=issues)
        return GateCheckResult(passed=True)

    def _gate_phase3(self, output: dict[str, Any]) -> GateCheckResult:
        spec = self._as_dict(output.get("abstract_spec"))
        dashboard = self._as_dict(spec.get("dashboard_spec"))
        pages = dashboard.get("pages") if isinstance(dashboard.get("pages"), list) else []

        issues: list[str] = []
        for page in pages:
            page_d = self._as_dict(page)
            visuals = page_d.get("visuals") if isinstance(page_d.get("visuals"), list) else []
            for visual in visuals:
                visual_d = self._as_dict(visual)
                vid = str(visual_d.get("id") or visual_d.get("source_worksheet") or "unknown")
                binding = self._as_dict(visual_d.get("data_binding"))
                axes = self._as_dict(binding.get("axes"))
                vtype = str(visual_d.get("type") or "").lower()

                if not binding:
                    issues.append(f"Phase3 gate failed: visual {vid} has no data_binding.")
                    continue
                if not axes and vtype not in {"textbox"}:
                    issues.append(f"Phase3 gate failed: visual {vid} has no axes binding.")
                    continue

                is_chart_like = any(token in vtype for token in ("chart", "bar", "line", "pie", "area", "scatter", "treemap"))
                if is_chart_like and not (axes.get("y") or axes.get("value") or axes.get("values")):
                    issues.append(f"Phase3 gate failed: chart visual {vid} has no measure axis.")

        if issues:
            return GateCheckResult(passed=False, issues=issues)
        return GateCheckResult(passed=True)

    def _gate_phase5(self, output: dict[str, Any]) -> GateCheckResult:
        export_result = self._as_dict(output.get("export_result"))
        validation = self._as_dict(export_result.get("validation"))
        content_bytes = int(export_result.get("content_bytes") or 0)

        issues: list[str] = []
        if not bool(validation.get("is_valid", False)):
            issues.append("Phase5 gate failed: RDL validation.is_valid is false.")
        if content_bytes <= 0:
            issues.append("Phase5 gate failed: exported RDL payload is empty.")

        if issues:
            return GateCheckResult(passed=False, issues=issues)
        return GateCheckResult(passed=True)

    def _gate_runtime_validation(self, output: dict[str, Any]) -> GateCheckResult:
        runtime = self._as_dict(output.get("runtime_validation"))
        status = str(runtime.get("status") or "failure").lower()
        issues: list[str] = []

        if status != "success":
            issues.append("Runtime validation failed: generated RDL could not be opened safely.")

        errs = runtime.get("errors") if isinstance(runtime.get("errors"), list) else []
        for err in errs:
            err_d = self._as_dict(err)
            msg = str(err_d.get("message") or "runtime validation error")
            issues.append(f"Runtime validation issue: {msg}")

        if issues:
            return GateCheckResult(passed=False, issues=issues)
        return GateCheckResult(passed=True)

    def _collect_dimension_names(self, node: Any) -> set[str]:
        names: set[str] = set()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                role = str(value.get("role") or value.get("semantic_role") or "").lower()
                name = str(value.get("name") or value.get("column") or "").strip()
                if role in {"dimension", "categorical", "text"} and name:
                    names.add(name)
                for child in value.values():
                    walk(child)
                return
            if isinstance(value, list):
                for child in value:
                    walk(child)

        walk(node)
        return names

    def _collect_measure_expressions(self, node: Any) -> list[str]:
        exprs: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                role = str(value.get("role") or value.get("semantic_role") or "").lower()
                for key in ("expression", "tableau_expression", "rdl_expression"):
                    expr = value.get(key)
                    if isinstance(expr, str) and expr.strip() and (role == "measure" or self._contains_agg(expr)):
                        exprs.append(expr.strip())
                for child in value.values():
                    walk(child)
                return
            if isinstance(value, list):
                for child in value:
                    walk(child)

        walk(node)
        return exprs

    def _contains_agg(self, expr: str) -> bool:
        e = expr.lower()
        return any(f"{fn}(" in e for fn in self.AGG_FUNCS)

    def _is_aggregating_dimension(self, expr_low: str, dim_low: str) -> bool:
        if not dim_low:
            return False
        escaped = re.escape(dim_low)
        return any(re.search(rf"\b{fn}\s*\([^\)]*\b{escaped}\b", expr_low) is not None for fn in self.AGG_FUNCS)

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="json")
            return dumped if isinstance(dumped, dict) else {}
        return {}
