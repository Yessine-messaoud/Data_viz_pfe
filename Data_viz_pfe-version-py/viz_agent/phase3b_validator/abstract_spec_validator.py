from __future__ import annotations

from viz_agent.models.validation import Issue, ValidationReport
from viz_agent.chart_type_registry import allowed_series_overrides, is_chart_logical_type


SPECIFIC_CHART_RDL_TYPES = {
    "columnchart",
    "linechart",
    "piechart",
    "treemap",
    "scatterchart",
}


class AbstractSpecValidator:
    @staticmethod
    def _rdl_type(visual) -> str:
        return str(getattr(visual, "rdl_type", getattr(visual, "type", "tablix"))).strip().lower()

    def validate(self, spec) -> ValidationReport:
        errors: list[Issue] = []
        warnings: list[Issue] = []

        self._check_unknown_tables(spec, errors)
        self._check_raw_column_ids(spec, errors)
        self._check_empty_rdl_datasets(spec, errors)
        self._check_fact_table(spec, errors)
        self._check_duplicate_pages(spec, warnings)
        self._check_empty_axes(spec, warnings)
        self._check_custom_visual_types(spec, warnings)
        self._check_generic_chart_types(spec, errors)
        self._check_visual_type_override_registry(spec, errors)
        self._check_semantic_binding_blockers(spec, errors)
        self._check_ghost_tables(spec, warnings)

        return ValidationReport(
            score=self._compute_score(errors, warnings),
            errors=errors,
            warnings=warnings,
            can_proceed=len(errors) == 0,
        )

    def _check_unknown_tables(self, spec, errors: list[Issue]) -> None:
        known = {table.name for table in spec.data_lineage.tables}
        if "unknown_table" in known:
            errors.append(
                Issue(
                    code="M_TABLE",
                    severity="error",
                    message="Table inconnue detectee dans le lineage",
                    fix="Verifier le mapping des datasources",
                )
            )

    def _check_raw_column_ids(self, spec, errors: list[Issue]) -> None:
        for table in spec.data_lineage.tables:
            for col in table.columns:
                if str(col.name).startswith("[") and str(col.name).endswith("]"):
                    errors.append(
                        Issue(
                            code="M_COL",
                            severity="error",
                            message=f"Column ID brut detecte: {col.name}",
                            fix="Normaliser les noms de colonnes",
                        )
                    )
                    return

    def _check_empty_rdl_datasets(self, spec, errors: list[Issue]) -> None:
        if not spec.rdl_datasets:
            errors.append(
                Issue(
                    code="R001",
                    severity="error",
                    message="rdl_datasets vide - Phase 0 (DataSource Layer) non executee",
                    fix="Executer HyperExtractor / CSVLoader avant le parsing",
                )
            )

    def _check_fact_table(self, spec, errors: list[Issue]) -> None:
        declared = spec.semantic_model.fact_table
        if declared in ("unknown_table", "customer_data", ""):
            errors.append(
                Issue(
                    code="M_FACT",
                    severity="error",
                    message=f"fact_table='{declared}' probablement incorrect",
                    fix="Utiliser detect_fact_table() avec scoring FK",
                    auto_fix="sales_data",
                )
            )

    def _check_duplicate_pages(self, spec, warnings: list[Issue]) -> None:
        names = [page.name for page in spec.dashboard_spec.pages]
        if len(names) != len(set(names)):
            warnings.append(
                Issue(
                    code="DUP_PAGE",
                    severity="warning",
                    message="Pages dupliquees detectees",
                )
            )

    def _check_empty_axes(self, spec, warnings: list[Issue]) -> None:
        for page in spec.dashboard_spec.pages:
            for visual in page.visuals:
                if not visual.data_binding.axes and self._rdl_type(visual) != "textbox":
                    warnings.append(
                        Issue(
                            code="EMPTY_AXES",
                            severity="warning",
                            message=f"Visual sans axes: {visual.id}",
                        )
                    )
                    return

    def _check_custom_visual_types(self, spec, warnings: list[Issue]) -> None:
        allowed = {"tablix", "textbox", "map"} | SPECIFIC_CHART_RDL_TYPES
        for page in spec.dashboard_spec.pages:
            for visual in page.visuals:
                rdl_type = self._rdl_type(visual)
                if rdl_type not in allowed and not rdl_type.endswith("chart"):
                    warnings.append(
                        Issue(
                            code="VTYPE",
                            severity="warning",
                            message=f"Type visuel non standard: {visual.type} (rdl_type={rdl_type})",
                        )
                    )
                    return

    def _check_generic_chart_types(self, spec, errors: list[Issue]) -> None:
        for page in spec.dashboard_spec.pages:
            for visual in page.visuals:
                logical_type = str(visual.type).strip().lower()
                rdl_type = self._rdl_type(visual)
                if logical_type == "chart" or rdl_type == "chart":
                    errors.append(
                        Issue(
                            code="VTYPE_GENERIC",
                            severity="error",
                            message=(
                                f"Type visuel generique interdit dans abstract spec: "
                                f"{visual.id} (type={logical_type}, rdl_type={rdl_type})"
                            ),
                            fix="Utiliser un type metier explicite (bar/line/pie/treemap/scatter/table/kpi/map).",
                        )
                    )
                    return

    def _check_visual_type_override_registry(self, spec, errors: list[Issue]) -> None:
        allowed_overrides = allowed_series_overrides()
        chart_family = {"bar", "line", "scatter", "pie", "treemap"}
        for page in spec.dashboard_spec.pages:
            for visual in page.visuals:
                logical_type = str(visual.type).strip().lower()
                rdl_type = self._rdl_type(visual)
                override = str(getattr(visual.data_binding, "visual_type_override", "") or "").strip().lower()

                if not override:
                    continue

                if override not in allowed_overrides and logical_type in chart_family:
                    errors.append(
                        Issue(
                            code="VTYPE_OVERRIDE_INVALID",
                            severity="error",
                            message=(
                                f"visual_type_override invalide '{override}' pour visual {visual.id}"
                            ),
                            fix=(
                                "Utiliser un override autorise: column|line|scatter|bar|area|pie"
                            ),
                        )
                    )
                    return

    def _semantic_index(self, spec) -> tuple[dict[tuple[str, str], tuple[str, str]], dict[str, tuple[str, str]]]:
        by_table_and_col: dict[tuple[str, str], tuple[str, str]] = {}
        by_col: dict[str, tuple[str, str]] = {}
        collisions: set[str] = set()

        for entity in getattr(spec.semantic_model, "entities", []) or []:
            table_name = str(getattr(entity, "name", "") or "").strip()
            for column in getattr(entity, "columns", []) or []:
                col_name = str(getattr(column, "name", "") or "").strip()
                if not col_name:
                    continue
                role = str(getattr(column, "role", "unknown") or "unknown").strip().lower()
                pbi_type = str(getattr(column, "pbi_type", getattr(column, "data_type", "text")) or "text").strip().lower()

                by_table_and_col[(table_name.lower(), col_name.lower())] = (role, pbi_type)

                if col_name.lower() not in by_col:
                    by_col[col_name.lower()] = (role, pbi_type)
                elif by_col[col_name.lower()] != (role, pbi_type):
                    collisions.add(col_name.lower())

        for col_name in collisions:
            by_col.pop(col_name, None)
        return by_table_and_col, by_col

    def _resolve_ref_role_type(self, ref, by_table_and_col, by_col) -> tuple[str, str]:
        if ref is None:
            return "unknown", ""

        if hasattr(ref, "table") and hasattr(ref, "column"):
            table = str(getattr(ref, "table", "") or "").strip().lower()
            column = str(getattr(ref, "column", "") or "").strip().lower()
            if table and column and (table, column) in by_table_and_col:
                return by_table_and_col[(table, column)]
            if column and column in by_col:
                return by_col[column]

        if hasattr(ref, "name"):
            name = str(getattr(ref, "name", "") or "").strip().lower()
            if name in by_col:
                return by_col[name]

        return "unknown", ""

    def _is_numeric_type(self, pbi_type: str) -> bool:
        normalized = str(pbi_type or "").strip().lower()
        return normalized in {"int", "integer", "decimal", "float", "double", "number", "currency", "money"}

    def _check_semantic_binding_blockers(self, spec, errors: list[Issue]) -> None:
        by_table_and_col, by_col = self._semantic_index(spec)
        chart_family = {"bar", "line", "scatter", "pie", "treemap"}

        for page in spec.dashboard_spec.pages:
            for visual in page.visuals:
                logical_type = str(getattr(visual, "type", "") or "").strip().lower()
                rdl_type = self._rdl_type(visual)
                is_chart = logical_type in chart_family or rdl_type.endswith("chart") or rdl_type == "treemap"
                if not is_chart:
                    continue

                axes = getattr(visual.data_binding, "axes", {}) or {}
                y_ref = axes.get("y")
                y_role, y_type = self._resolve_ref_role_type(y_ref, by_table_and_col, by_col)
                if y_ref is not None and y_role not in {"measure", "unknown"}:
                    errors.append(
                        Issue(
                            code="SEM_BIND_Y_ROLE",
                            severity="error",
                            message=f"Visual chart {visual.id} utilise un axe Y non mesure",
                            fix="Binder l axe Y a une mesure numerique",
                        )
                    )
                    return
                if y_ref is not None and y_type and not self._is_numeric_type(y_type):
                    errors.append(
                        Issue(
                            code="SEM_BIND_Y_NUMERIC",
                            severity="error",
                            message=f"Visual chart {visual.id} utilise une mesure non numerique ({y_type})",
                            fix="Utiliser une mesure numerique pour l axe Y",
                        )
                    )
                    return

                for axis_name in ("x", "color", "detail"):
                    axis_ref = axes.get(axis_name)
                    axis_role, _axis_type = self._resolve_ref_role_type(axis_ref, by_table_and_col, by_col)
                    if axis_ref is not None and axis_role == "measure":
                        errors.append(
                            Issue(
                                code="SEM_BIND_DIM_AGG",
                                severity="error",
                                message=f"Visual chart {visual.id} utilise une mesure sur axe {axis_name} (dimension attendue)",
                                fix="Utiliser une dimension sur x/color/detail ou ajuster l agregation",
                            )
                        )
                        return

                if rdl_type.endswith("chart") and not is_chart_logical_type(logical_type):
                    errors.append(
                        Issue(
                            code="VTYPE_RDL_MISMATCH",
                            severity="error",
                            message=(
                                f"Incoherence type visuel/rdl: type={logical_type}, rdl_type={rdl_type}"
                            ),
                            fix="Utiliser un type metier chart-compatible (bar/line/scatter/pie/treemap)",
                        )
                    )
                    return

    def _check_ghost_tables(self, spec, warnings: list[Issue]) -> None:
        for table in spec.data_lineage.tables:
            if table.row_count == 0 and table.columns:
                warnings.append(
                    Issue(
                        code="GHOST_TABLE",
                        severity="warning",
                        message=f"Table potentiellement fantome: {table.name}",
                    )
                )
                return

    def _compute_score(self, errors: list[Issue], warnings: list[Issue]) -> int:
        return max(0, 100 - len(errors) * 20 - len(warnings) * 5)
