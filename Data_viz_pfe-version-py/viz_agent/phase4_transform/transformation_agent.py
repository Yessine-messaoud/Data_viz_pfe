from __future__ import annotations

import re
from typing import Any, Dict, Optional

from viz_agent.models.abstract_spec import DataLineageSpec, SemanticModel

from .calc_field_translator import CalcFieldTranslator
from .compatibility_manager import CompatibilityManager
from .dataset_builder import DatasetBuilder
from .lineage_tracker import LineageTracker
from .transformation_fixer import TransformationFixer
from .visual_compatibility import VisualCompatibility
from .agent.validation_hook import ValidationHook


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


class TransformationAgent:
    """Deterministic Phase 4 transformation contract layer."""

    def __init__(self, orchestrator=None, validation_agent=None, lineage_agent=None, rules_config=None):
        self.orchestrator = orchestrator
        self.validation_hook = ValidationHook(validation_agent)
        self.lineage_tracker = LineageTracker(lineage_agent)
        self.calc_translator = CalcFieldTranslator()
        self.dataset_builder = DatasetBuilder()
        self.visual_compatibility = VisualCompatibility()
        self.transformation_fixer = TransformationFixer()
        self.compatibility_manager = CompatibilityManager(rules_config)

    def transform(self, abstract_spec: Dict, target_tool: str, context: Dict, intent: Optional[Dict] = None) -> Dict:
        transform_log: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: list[str] = []

        try:
            if not isinstance(abstract_spec, dict):
                return {"error": "abstract_spec must be a dictionary", "transform_log": transform_log}

            semantic_model = self._semantic_model(abstract_spec.get("semantic_model"))
            lineage = self._data_lineage(abstract_spec.get("data_lineage"))

            dataset_result = self.dataset_builder.build(abstract_spec, semantic_model, lineage)
            transform_log.extend(dataset_result.build_log)
            warnings.extend(dataset_result.warnings)

            measures = self._translate_measures(semantic_model)
            transform_log.extend(self._measure_logs)
            warnings.extend(self._measure_warnings)

            visuals = self._build_visuals(abstract_spec, semantic_model, dataset_result, target_tool)
            warnings.extend(self._visual_warnings)
            transform_log.extend(self._visual_logs)

            tool_model: Dict[str, Any] = {
                "target_tool": str(target_tool or "").upper(),
                "datasets": dataset_result.datasets,
                "visuals": visuals,
                "measures": measures,
                "parameters": self._safe_list(abstract_spec.get("parameters")),
                "filters": self._safe_list((abstract_spec.get("dashboard_spec") or {}).get("global_filters")),
                "semantic_model": semantic_model,
                "lineage": lineage,
                "meta": {
                    "source_spec_id": abstract_spec.get("id", ""),
                    "source_spec_version": abstract_spec.get("version", ""),
                    "intent": intent or {},
                },
            }

            safe_context = dict(context or {}) if isinstance(context, dict) else {}
            tool_model, compatibility_log = self.compatibility_manager.resolve(tool_model, target_tool, safe_context | {"semantic_model": semantic_model})
            transform_log.extend(compatibility_log)

            strict_issues = self._strict_validate(tool_model)
            validation_results = self.validation_hook.validate(tool_model)
            validation_results.extend(strict_issues)
            tool_model["validation_results"] = validation_results

            for issue in validation_results:
                message = str(issue.get("message") or "")
                if issue.get("severity") == "error":
                    errors.append(message)
                else:
                    warnings.append(message)

            lineage_events = self.lineage_tracker.capture(tool_model)
            tool_model["lineage_events"] = lineage_events
            tool_model["transform_log"] = transform_log
            tool_model["warnings"] = self._dedupe(warnings)
            tool_model["errors"] = self._dedupe(errors)

            if errors and self.orchestrator:
                recovery = self.orchestrator.handle_transformation_failure(abstract_spec, target_tool, "; ".join(errors), transform_log)
                transform_log.append({"step": "recovery", "message": recovery})

            return tool_model
        except Exception as exc:
            transform_log.append({"step": "error", "message": str(exc)})
            if self.orchestrator:
                recovery = self.orchestrator.handle_transformation_failure(abstract_spec, target_tool, str(exc), transform_log)
                transform_log.append({"step": "recovery", "message": recovery})
            return {"error": str(exc), "transform_log": transform_log, "warnings": warnings, "errors": errors}

    def _semantic_model(self, value: Any) -> SemanticModel:
        if isinstance(value, SemanticModel):
            return value
        return SemanticModel.model_validate(_as_dict(value))

    def _data_lineage(self, value: Any) -> DataLineageSpec:
        if isinstance(value, DataLineageSpec):
            return value
        return DataLineageSpec.model_validate(_as_dict(value))

    def _safe_list(self, value: Any) -> list[Any]:
        return list(value) if isinstance(value, list) else []

    def _translate_measures(self, semantic_model: SemanticModel) -> list[dict[str, Any]]:
        self._measure_logs: list[dict[str, Any]] = []
        self._measure_warnings: list[str] = []
        measures: list[dict[str, Any]] = []
        dimension_names = self._dimension_name_set(semantic_model)
        measures_source = _as_dict(semantic_model).get("measures", []) or getattr(semantic_model, "measures", []) or []
        for measure in measures_source:
            measure_dict = _as_dict(measure)
            name = str(measure_dict.get("name") or getattr(measure, "name", "") or "").strip()
            expression = str(measure_dict.get("expression") or getattr(measure, "expression", "") or "").strip()
            if self._is_invalid_dimension_aggregation(expression, dimension_names):
                self._measure_warnings.append(f"{name}: removed invalid aggregation on dimension")
                self._measure_logs.append(
                    {
                        "step": "measure_filter",
                        "measure": name,
                        "status": "removed_invalid_dimension_aggregation",
                        "expression": expression,
                    }
                )
                continue
            translated = self.calc_translator.translate(expression, semantic_model, max_retries=1, deterministic_first=True)
            report = getattr(self.calc_translator, "last_report", None)
            warnings = list(getattr(report, "warnings", [])) if report is not None else []
            if translated.startswith("/* UNTRANSLATABLE"):
                self._measure_warnings.append(f"{name}: fallback expression used")
            self._measure_warnings.extend(warnings)
            self._measure_logs.append({"step": "calculation_translation", "measure": name, "expression": expression, "translated": translated})
            measures.append(
                {
                    "name": name,
                    "expression": expression,
                    "translated_expression": translated,
                    "rdl_expression": translated,
                    "source_columns": measure_dict.get("source_columns", []),
                    "pattern": measure_dict.get("pattern", ""),
                    "template_args": measure_dict.get("template_args", {}),
                    "tableau_expression": measure_dict.get("tableau_expression", expression),
                }
            )
        return measures

    def _build_visuals(self, abstract_spec: Dict[str, Any], semantic_model: SemanticModel, dataset_result: Any, target_tool: str) -> list[dict[str, Any]]:
        self._visual_logs: list[dict[str, Any]] = []
        self._visual_warnings: list[str] = []
        dataset_by_visual = dataset_result.visual_assignments if hasattr(dataset_result, "visual_assignments") else {}
        datasets_by_name = {str(dataset.get("name") or "").lower(): dataset for dataset in dataset_result.datasets}

        visuals: list[dict[str, Any]] = []
        dashboard = _as_dict(abstract_spec.get("dashboard_spec"))
        for page in dashboard.get("pages", []) or []:
            page_dict = _as_dict(page)
            for visual in page_dict.get("visuals", []) or []:
                visual_dict = _as_dict(visual)
                visual_id = str(visual_dict.get("id") or visual_dict.get("source_worksheet") or "visual").strip()
                dataset_name = dataset_by_visual.get(visual_id, "")
                dataset = datasets_by_name.get(str(dataset_name).lower())
                candidate = dict(visual_dict)
                candidate["dataset"] = dataset_name
                candidate["dataset_name"] = dataset_name

                compatibility = self.visual_compatibility.normalize_visual(candidate, dataset, target_tool, semantic_model)
                corrected = compatibility.visual
                corrected = self._normalize_visual_type(corrected)
                if not compatibility.supported:
                    fix_result = self.transformation_fixer.fix(corrected, dataset, semantic_model, target_tool)
                    corrected = fix_result.visual
                    corrected = self._normalize_visual_type(corrected)
                    if fix_result.dataset is not None and dataset_name:
                        datasets_by_name[dataset_name.lower()] = fix_result.dataset
                    self._visual_warnings.extend(fix_result.warnings)
                    self._visual_logs.extend(
                        {
                            "step": "visual_correction",
                            "status": "applied",
                            "message": message,
                            "visual_id": visual_id,
                        }
                        for message in fix_result.corrections
                    )

                if not dataset_name:
                    self._visual_warnings.append(f"{visual_id}: no dataset assigned")

                corrected = self._sanitize_size_binding(corrected, semantic_model)

                self._visual_warnings.extend(compatibility.warnings)
                self._visual_logs.append(
                    {
                        "step": "visual_mapping",
                        "status": "done" if compatibility.supported else "fallback",
                        "visual_id": visual_id,
                        "dataset": dataset_name,
                        "tool_visual_type": corrected.get("tool_visual_type", corrected.get("rdl_type", "")),
                    }
                )
                visuals.append(corrected)

        return visuals

    def _normalize_visual_type(self, visual: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(visual, dict):
            return visual
        current = str(visual.get("tool_visual_type") or visual.get("rdl_type") or visual.get("type") or "").strip().lower()
        if current == "chart":
            visual["tool_visual_type"] = "columnchart"
            visual["rdl_type"] = "columnchart"
            visual["type"] = "columnchart"
        return visual

    def _sanitize_size_binding(self, visual: dict[str, Any], semantic_model: SemanticModel) -> dict[str, Any]:
        if not isinstance(visual, dict):
            return visual
        binding = _as_dict(visual.get("data_binding"))
        axes = _as_dict(binding.get("axes"))
        if not axes or "size" not in axes:
            return visual

        size_value = axes.get("size")
        dim_names = self._dimension_name_set(semantic_model)
        raw = ""
        if isinstance(size_value, dict):
            raw = str(size_value.get("column") or size_value.get("name") or "").strip()
        else:
            raw = str(size_value or "").strip()

        if raw and raw.lower() in dim_names:
            axes.pop("size", None)
            binding["axes"] = axes
            visual["data_binding"] = binding
            if not hasattr(self, "_visual_warnings"):
                self._visual_warnings = []
            self._visual_warnings.append(f"{visual.get('id', 'visual')}: removed dimension from size axis ({raw})")
        return visual

    def _dimension_name_set(self, semantic_model: SemanticModel) -> set[str]:
        names: set[str] = set()
        model_dict = _as_dict(semantic_model)

        for entity in model_dict.get("entities", []) if isinstance(model_dict.get("entities"), list) else []:
            entity_d = _as_dict(entity)
            for column in entity_d.get("columns", []) if isinstance(entity_d.get("columns"), list) else []:
                col = _as_dict(column)
                if str(col.get("role") or "").lower() == "dimension":
                    name = str(col.get("name") or "").strip()
                    if name:
                        names.add(name.lower())

        for dim in model_dict.get("dimensions", []) if isinstance(model_dict.get("dimensions"), list) else []:
            dim_d = _as_dict(dim)
            name = str(dim_d.get("name") or dim_d.get("column") or "").strip()
            if name:
                names.add(name.lower())

        return names

    def _is_invalid_dimension_aggregation(self, expression: str, dimension_names: set[str]) -> bool:
        expr = str(expression or "")
        if not expr or not dimension_names:
            return False
        low = expr.lower()
        for dim in dimension_names:
            if any(re.search(rf"\b{fn}\s*\([^\)]*\b{re.escape(dim)}\b", low) for fn in ("sum", "avg", "average", "min", "max")):
                return True
        return False

    def _strict_validate(self, tool_model: Dict[str, Any]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        datasets = tool_model.get("datasets", []) if isinstance(tool_model, dict) else []
        visuals = tool_model.get("visuals", []) if isinstance(tool_model, dict) else []

        if not datasets:
            issues.append({"severity": "error", "code": "P4_S001", "message": "No dataset generated.", "field": "datasets"})

        for idx, dataset in enumerate(datasets if isinstance(datasets, list) else []):
            if not isinstance(dataset, dict):
                issues.append({"severity": "error", "code": "P4_S002", "message": "Dataset must be a dict.", "field": f"datasets[{idx}]"})
                continue
            if not str(dataset.get("name") or "").strip():
                issues.append({"severity": "error", "code": "P4_S003", "message": "Dataset name missing.", "field": f"datasets[{idx}].name"})
            fields = dataset.get("fields", [])
            if not fields:
                issues.append({"severity": "error", "code": "P4_S004", "message": "Dataset has no fields.", "field": f"datasets[{idx}].fields"})
            if str(dataset.get("query") or "").strip() and "SELECT *" in str(dataset.get("query") or "").upper():
                issues.append({"severity": "error", "code": "P4_S005", "message": "SELECT * is forbidden.", "field": f"datasets[{idx}].query"})

        supported_visual_types = {"columnchart", "linechart", "piechart", "treemap", "scatterchart", "tablix", "textbox", "map"}
        for idx, visual in enumerate(visuals if isinstance(visuals, list) else []):
            if not isinstance(visual, dict):
                issues.append({"severity": "error", "code": "P4_S010", "message": "Visual must be a dict.", "field": f"visuals[{idx}]"})
                continue
            if not str(visual.get("dataset") or visual.get("dataset_name") or "").strip():
                issues.append({"severity": "error", "code": "P4_S011", "message": "Visual missing dataset assignment.", "field": f"visuals[{idx}].dataset"})
            visual_type = str(visual.get("tool_visual_type") or visual.get("rdl_type") or visual.get("type") or "").strip().lower()
            if visual_type and visual_type not in supported_visual_types:
                issues.append({"severity": "error", "code": "P4_S012", "message": f"Unsupported visual type '{visual_type}'.", "field": f"visuals[{idx}].tool_visual_type"})
            binding = _as_dict(visual.get("data_binding"))
            axes = _as_dict(binding.get("axes"))
            if not axes and visual_type not in {"textbox"}:
                issues.append({"severity": "warning", "code": "P4_S013", "message": "Visual has no axes.", "field": f"visuals[{idx}].data_binding.axes"})

        return issues

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = str(value or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(str(value).strip())
        return ordered
