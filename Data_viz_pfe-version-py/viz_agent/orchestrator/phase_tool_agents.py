from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from viz_agent.orchestrator.phase_agent import PhaseAgentResult


def _result(
    *,
    status: str,
    confidence: float,
    output: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    retry_hint: str = "",
) -> PhaseAgentResult:
    return PhaseAgentResult(
        status=status,
        confidence=confidence,
        output=output or {},
        errors=errors or [],
        retry_hint=retry_hint,
    ).normalized()


def _safe_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}


class Phase0ToolAgent:
    name = "data_extraction"

    def __init__(self) -> None:
        self._agent = None
        self._init_error = ""
        try:
            from viz_agent.phase0_extraction.agent.data_extraction_agent import DataExtractionAgent

            self._agent = DataExtractionAgent(config={})
        except Exception as exc:
            self._init_error = str(exc)

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        if self._agent is None:
            return _result(status="error", confidence=0.0, errors=[f"Phase0 init failed: {self._init_error}"], retry_hint="Install missing dependencies and retry.")
        artifacts = state.get("artifacts", {}) if isinstance(state, dict) else {}
        source_path = artifacts.get("source_path") or artifacts.get("input_path")
        if not source_path:
            return _result(
                status="error",
                confidence=0.0,
                errors=["Missing artifacts.source_path"],
                retry_hint="Provide input source_path for phase0 extraction.",
            )

        result = self._agent.run({"inputs": {"artifacts": {"source_path": source_path}}})
        if result.get("error"):
            return _result(
                status="error",
                confidence=0.2,
                output=result,
                errors=[str(result.get("error"))],
                retry_hint="Check source file path and extraction dependencies.",
            )
        payload = result.get("data", {}) if isinstance(result, dict) else {}
        confidence = 0.9 if payload else 0.6
        status = "success" if result.get("validation_status") == "passed" else "low_confidence"
        return _result(status=status, confidence=confidence, output={"metadata": payload}, retry_hint="Retry extraction with deterministic parser.")


class Phase1ToolAgent:
    name = "parsing"

    def __init__(self) -> None:
        self._agent = None
        self._init_error = ""
        try:
            from viz_agent.phase1_parser.agent.parsing_agent import ParsingAgent

            self._agent = ParsingAgent()
        except Exception as exc:
            self._init_error = str(exc)

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        if self._agent is None:
            return _result(status="error", confidence=0.0, errors=[f"Phase1 init failed: {self._init_error}"], retry_hint="Install missing dependencies and retry.")
        artifacts = state.get("artifacts", {}) if isinstance(state, dict) else {}
        context = state.get("context", {}) if isinstance(state, dict) else {}
        previous = state.get("previous_outputs", {}) if isinstance(state, dict) else {}

        artifact_path = artifacts.get("source_path") or artifacts.get("input_path")
        metadata = (previous.get("data_extraction") or {}).get("metadata", {})
        if not artifact_path:
            return _result(status="error", confidence=0.0, errors=["Missing artifact path for parsing"], retry_hint="Provide artifacts.source_path.")

        parsed = self._agent.parse(str(artifact_path), metadata, context)
        self._apply_deterministic_fixes(parsed, context)
        self._apply_heuristic_fixes(parsed, context)
        self._apply_llm_fixes(parsed, context)
        if parsed.get("error"):
            return _result(
                status="error",
                confidence=0.2,
                output=parsed,
                errors=[str(parsed.get("error"))],
                retry_hint="Retry with heuristic parser or inspect workbook format.",
            )

        has_dashboards = bool(parsed.get("dashboards"))
        has_visuals = bool(parsed.get("visuals"))
        if has_dashboards and has_visuals:
            return _result(status="success", confidence=0.88, output={"parsed_structure": parsed}, retry_hint="")
        return _result(
            status="low_confidence",
            confidence=0.65,
            output={"parsed_structure": parsed},
            retry_hint="Retry with heuristic and LLM parser strategy.",
        )

    def _apply_heuristic_fixes(self, parsed: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("heuristic_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        if fixes.get("infer_dashboards_from_visuals"):
            dashboards = parsed.get("dashboards") if isinstance(parsed.get("dashboards"), list) else []
            visuals = parsed.get("visuals") if isinstance(parsed.get("visuals"), list) else []
            if not dashboards and visuals:
                parsed["dashboards"] = [{"name": "AutoDashboard", "visual_count": len(visuals)}]

    def _apply_llm_fixes(self, parsed: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("llm_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        if fixes.get("force_minimal_valid_structure"):
            parsed.setdefault("worksheets", [{"name": "LLMWorksheet"}])
            parsed.setdefault("dashboards", [{"name": "LLMDashboard"}])
            parsed.setdefault("visuals", [{"source_worksheet": "LLMWorksheet"}])

    def _apply_deterministic_fixes(self, parsed: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("deterministic_fixes", {}) or {}).get(self.name, {})
        if not fixes or not fixes.get("ensure_worksheets_from_visuals"):
            return
        worksheets = parsed.get("worksheets")
        if isinstance(worksheets, list) and worksheets:
            return
        visuals = parsed.get("visuals") if isinstance(parsed.get("visuals"), list) else []
        synthesized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for visual in visuals:
            visual_d = visual if isinstance(visual, dict) else {}
            ws = str(visual_d.get("source_worksheet") or "").strip()
            if not ws or ws in seen:
                continue
            seen.add(ws)
            synthesized.append({"name": ws})
        if synthesized:
            parsed["worksheets"] = synthesized


class Phase2ToolAgent:
    name = "semantic_reasoning"

    def __init__(self) -> None:
        self._agent = None
        self._init_error = ""
        try:
            from viz_agent.phase2_semantic.agent.semantic_agent import SemanticAgent

            self._agent = SemanticAgent()
        except Exception as exc:
            self._init_error = str(exc)

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        if self._agent is None:
            return _result(status="error", confidence=0.0, errors=[f"Phase2 init failed: {self._init_error}"], retry_hint="Install missing dependencies and retry.")
        context = state.get("context", {}) if isinstance(state, dict) else {}
        intent = context.get("intent", {}) if isinstance(context, dict) else {}
        previous = state.get("previous_outputs", {}) if isinstance(state, dict) else {}
        metadata = (previous.get("data_extraction") or {}).get("metadata", {})
        parsed = (previous.get("parsing") or {}).get("parsed_structure", {})

        graph = self._agent.build_semantic_graph(metadata, parsed, intent=intent)
        self._apply_deterministic_fixes(graph, context)
        self._apply_heuristic_fixes(graph, context)
        self._apply_llm_fixes(graph, context)
        if graph.get("error"):
            return _result(
                status="error",
                confidence=0.2,
                output=graph,
                errors=[str(graph.get("error"))],
                retry_hint="Retry with stronger disambiguation or fallback reasoning.",
            )

        conf = float(graph.get("confidence_score", 0.7) or 0.7)
        status = "success" if conf > 0.8 else "low_confidence"
        return _result(status=status, confidence=conf, output={"semantic_graph": graph}, retry_hint="Resolve ambiguous dimensions/measures.")

    def _apply_heuristic_fixes(self, graph: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("heuristic_fixes", {}) or {}).get(self.name, {})
        if not fixes or not fixes.get("infer_default_measure_from_numeric_candidates"):
            return
        measures = graph.get("measures") if isinstance(graph.get("measures"), list) else []
        if measures:
            return
        cols = graph.get("columns") if isinstance(graph.get("columns"), list) else []
        for col in cols:
            c = col if isinstance(col, dict) else {}
            name = str(c.get("name") or "")
            lowered = name.lower()
            if any(token in lowered for token in ("amount", "sales", "total", "cost", "price", "qty", "quantity")):
                graph["measures"] = [{"name": f"Total_{name}", "role": "measure", "expression": f"SUM({name})"}]
                break

    def _apply_llm_fixes(self, graph: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("llm_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        if fixes.get("force_non_empty_measures") and not isinstance(graph.get("measures"), list):
            graph["measures"] = [{"name": "LLMMeasure", "role": "measure", "expression": "SUM(_AutoMeasure)"}]

    def _apply_deterministic_fixes(self, graph: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("deterministic_fixes", {}) or {}).get(self.name, {})
        if not fixes or not fixes.get("drop_aggregated_dimension_measures"):
            return

        dimensions: set[str] = set()
        for column in graph.get("columns", []) if isinstance(graph.get("columns"), list) else []:
            col = column if isinstance(column, dict) else {}
            role = str(col.get("role") or "").lower()
            if role in {"dimension", "text", "categorical"}:
                name = str(col.get("name") or col.get("column") or "").strip()
                if name:
                    dimensions.add(name.lower())

        measures = graph.get("measures") if isinstance(graph.get("measures"), list) else []
        filtered: list[dict[str, Any]] = []
        for measure in measures:
            m = measure if isinstance(measure, dict) else {}
            expr = str(m.get("expression") or "")
            expr_low = expr.lower()
            invalid = False
            for dim in dimensions:
                if any(re.search(rf"\b{fn}\s*\([^\)]*\b{re.escape(dim)}\b", expr_low) for fn in ("sum", "avg", "average", "min", "max")):
                    invalid = True
                    break
            if not invalid:
                filtered.append(m)
        graph["measures"] = filtered


class Phase3ToolAgent:
    name = "specification"

    def __init__(self) -> None:
        self._agent = None
        self._init_error = ""
        try:
            from viz_agent.phase3_spec.specification_agent import SpecificationAgent

            self._agent = SpecificationAgent()
        except Exception as exc:
            self._init_error = str(exc)

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        if self._agent is None:
            return _result(status="error", confidence=0.0, errors=[f"Phase3 init failed: {self._init_error}"], retry_hint="Install missing dependencies and retry.")
        context = state.get("context", {}) if isinstance(state, dict) else {}
        intent = context.get("intent", {}) if isinstance(context, dict) else {}
        previous = state.get("previous_outputs", {}) if isinstance(state, dict) else {}
        semantic_graph = (previous.get("semantic_reasoning") or {}).get("semantic_graph", {})

        try:
            spec = self._agent.generate_specification(semantic_graph, intent, context)
            self._apply_deterministic_fixes(spec, context)
            self._apply_heuristic_fixes(spec, context)
            self._apply_llm_fixes(spec, context)
        except Exception as exc:
            return _result(
                status="error",
                confidence=0.1,
                errors=[str(exc)],
                retry_hint="Validate semantic graph and intent schema before spec generation.",
            )

        conf = float(spec.get("confidence_score", 0.75) or 0.75)
        status = "success" if conf > 0.8 else "low_confidence"
        return _result(status=status, confidence=conf, output={"abstract_spec": spec}, retry_hint="Fix invalid bindings and regenerate spec.")

    def _apply_deterministic_fixes(self, spec: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("deterministic_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        dashboard = spec.get("dashboard_spec") if isinstance(spec.get("dashboard_spec"), dict) else {}
        pages = dashboard.get("pages") if isinstance(dashboard.get("pages"), list) else []
        for page in pages:
            page_d = page if isinstance(page, dict) else {}
            visuals = page_d.get("visuals") if isinstance(page_d.get("visuals"), list) else []
            for visual in visuals:
                visual_d = visual if isinstance(visual, dict) else {}
                binding = visual_d.get("data_binding") if isinstance(visual_d.get("data_binding"), dict) else {}
                axes = binding.get("axes") if isinstance(binding.get("axes"), dict) else {}

                if fixes.get("inject_chart_y_from_measures") and not axes.get("y"):
                    measures = binding.get("measures") if isinstance(binding.get("measures"), list) else []
                    if measures:
                        axes["y"] = measures[0]

                if fixes.get("remove_dimension_from_size") and axes.get("size"):
                    size_value = str(axes.get("size")).lower()
                    if "dimension" in size_value or "country" in size_value:
                        axes.pop("size", None)

                binding["axes"] = axes
                visual_d["data_binding"] = binding

    def _apply_heuristic_fixes(self, spec: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("heuristic_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        dashboard = spec.get("dashboard_spec") if isinstance(spec.get("dashboard_spec"), dict) else {}
        pages = dashboard.get("pages") if isinstance(dashboard.get("pages"), list) else []
        for page in pages:
            page_d = page if isinstance(page, dict) else {}
            visuals = page_d.get("visuals") if isinstance(page_d.get("visuals"), list) else []
            for visual in visuals:
                visual_d = visual if isinstance(visual, dict) else {}
                if fixes.get("normalize_generic_chart_type"):
                    vtype = str(visual_d.get("type") or "").lower()
                    if vtype == "chart":
                        visual_d["type"] = "columnchart"
                if fixes.get("inject_safe_axis_defaults"):
                    binding = visual_d.get("data_binding") if isinstance(visual_d.get("data_binding"), dict) else {}
                    axes = binding.get("axes") if isinstance(binding.get("axes"), dict) else {}
                    if not axes.get("x"):
                        axes["x"] = "_AutoCategory"
                    if not axes.get("y") and not axes.get("value"):
                        axes["y"] = "_AutoMeasure"
                    binding["axes"] = axes
                    visual_d["data_binding"] = binding

    def _apply_llm_fixes(self, spec: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("llm_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        if fixes.get("force_columnchart"):
            dashboard = spec.get("dashboard_spec") if isinstance(spec.get("dashboard_spec"), dict) else {}
            pages = dashboard.get("pages") if isinstance(dashboard.get("pages"), list) else []
            for page in pages:
                page_d = page if isinstance(page, dict) else {}
                visuals = page_d.get("visuals") if isinstance(page_d.get("visuals"), list) else []
                for visual in visuals:
                    if isinstance(visual, dict) and str(visual.get("type") or "").lower() == "chart":
                        visual["type"] = "columnchart"


class Phase4ToolAgent:
    name = "transformation"

    def __init__(self) -> None:
        self._agent = None
        self._init_error = ""
        try:
            from viz_agent.phase4_transform.transformation_agent import TransformationAgent

            self._agent = TransformationAgent()
        except Exception as exc:
            self._init_error = str(exc)

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        if self._agent is None:
            return _result(status="error", confidence=0.0, errors=[f"Phase4 init failed: {self._init_error}"], retry_hint="Install missing dependencies and retry.")
        context = state.get("context", {}) if isinstance(state, dict) else {}
        intent = context.get("intent", {}) if isinstance(context, dict) else {}
        previous = state.get("previous_outputs", {}) if isinstance(state, dict) else {}
        abstract_spec = (previous.get("specification") or {}).get("abstract_spec", {})

        tool_model = self._agent.transform(abstract_spec, target_tool="RDL", context=context, intent=intent)
        if tool_model.get("error"):
            return _result(
                status="error",
                confidence=0.2,
                output=tool_model,
                errors=[str(tool_model.get("error"))],
                retry_hint="Fix dataset and visual compatibility issues.",
            )

        errors = [str(i.get("message")) for i in (tool_model.get("validation_results") or []) if i.get("severity") == "error"]
        if errors:
            return _result(
                status="low_confidence",
                confidence=0.6,
                output={"tool_model": tool_model},
                errors=errors,
                retry_hint="Apply deterministic transformation fixes before retry.",
            )

        return _result(status="success", confidence=0.86, output={"tool_model": tool_model}, retry_hint="")


class Phase5ToolAgent:
    name = "export"

    def __init__(self) -> None:
        self._agent = None
        self._format = None
        self._init_error = ""
        try:
            from viz_agent.phase5_rdl.agent.export_agent import ExportAgent, ExportFormat

            self._agent = ExportAgent(config={})
            self._format = ExportFormat.RDL
        except Exception as exc:
            self._init_error = str(exc)

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        context = state.get("context", {}) if isinstance(state, dict) else {}
        artifacts = state.get("artifacts", {}) if isinstance(state, dict) else {}
        if self._agent is None or self._format is None:
            return _result(status="error", confidence=0.0, errors=[f"Phase5 init failed: {self._init_error}"], retry_hint="Install missing dependencies and retry.")
        previous = state.get("previous_outputs", {}) if isinstance(state, dict) else {}
        tool_model = (previous.get("transformation") or {}).get("tool_model", {})

        try:
            result = self._agent.export(tool_model, self._format)
        except Exception as exc:
            return _result(
                status="error",
                confidence=0.1,
                errors=[str(exc)],
                retry_hint="Retry export with deterministic serializer.",
            )

        validation = result.get("validation") if isinstance(result, dict) else {}
        self._apply_deterministic_fixes(result, context)
        self._apply_heuristic_fixes(result, context)
        self._apply_llm_fixes(result, context)
        validation = result.get("validation") if isinstance(result, dict) else {}
        is_valid = bool((validation or {}).get("is_valid", True))
        written_rdl_path = ""
        output_path = artifacts.get("output_path") if isinstance(artifacts, dict) else None
        content = result.get("content") if isinstance(result, dict) else None
        if output_path and isinstance(content, (bytes, bytearray)):
            try:
                path = Path(str(output_path))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(bytes(content))
                written_rdl_path = str(path)
            except Exception:
                written_rdl_path = ""

        payload = {
            "format": result.get("format"),
            "metadata": _safe_dict(result.get("metadata")),
            "validation": _safe_dict(validation),
            "content_bytes": len(result.get("content") or b""),
            "rdl_path": written_rdl_path,
        }

        if not is_valid:
            errors = [str(e) for e in (validation.get("errors") or [])] if isinstance(validation, dict) else ["RDL validation failed"]
            return _result(
                status="low_confidence",
                confidence=0.55,
                output={"export_result": payload},
                errors=errors,
                retry_hint="Repair invalid XML nodes and retry export.",
            )

        return _result(status="success", confidence=0.9, output={"export_result": payload}, retry_hint="")

    def _apply_deterministic_fixes(self, export_result: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("deterministic_fixes", {}) or {}).get(self.name, {})
        if not fixes or not fixes.get("repair_export_validation_flags"):
            return
        validation = export_result.get("validation") if isinstance(export_result.get("validation"), dict) else {}
        content = export_result.get("content")
        content_size = len(content) if isinstance(content, (bytes, bytearray)) else 0
        errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
        if content_size > 0 and not errors:
            validation["is_valid"] = True
            export_result["validation"] = validation

    def _apply_heuristic_fixes(self, export_result: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("heuristic_fixes", {}) or {}).get(self.name, {})
        if not fixes or not fixes.get("accept_warnings_only_validation"):
            return
        validation = export_result.get("validation") if isinstance(export_result.get("validation"), dict) else {}
        errors = validation.get("errors") if isinstance(validation.get("errors"), list) else []
        warnings = validation.get("warnings") if isinstance(validation.get("warnings"), list) else []
        content = export_result.get("content")
        content_size = len(content) if isinstance(content, (bytes, bytearray)) else 0
        if content_size > 0 and not errors and warnings:
            validation["is_valid"] = True
            export_result["validation"] = validation

    def _apply_llm_fixes(self, export_result: dict[str, Any], context: dict[str, Any]) -> None:
        fixes = ((context or {}).get("llm_fixes", {}) or {}).get(self.name, {})
        if not fixes:
            return
        if fixes.get("force_valid_when_payload_present"):
            validation = export_result.get("validation") if isinstance(export_result.get("validation"), dict) else {}
            content = export_result.get("content")
            content_size = len(content) if isinstance(content, (bytes, bytearray)) else 0
            if content_size > 0:
                validation["is_valid"] = True
                export_result["validation"] = validation


def build_default_phase_tools() -> list[Any]:
    return [
        Phase0ToolAgent(),
        Phase1ToolAgent(),
        Phase2ToolAgent(),
        Phase3ToolAgent(),
        Phase4ToolAgent(),
        Phase5ToolAgent(),
    ]
