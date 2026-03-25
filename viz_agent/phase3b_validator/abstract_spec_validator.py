from __future__ import annotations

from viz_agent.models.validation import Issue, ValidationReport


class AbstractSpecValidator:
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
                if not visual.data_binding.axes and visual.type != "textbox":
                    warnings.append(
                        Issue(
                            code="EMPTY_AXES",
                            severity="warning",
                            message=f"Visual sans axes: {visual.id}",
                        )
                    )
                    return

    def _check_custom_visual_types(self, spec, warnings: list[Issue]) -> None:
        allowed = {"tablix", "chart", "textbox", "map"}
        for page in spec.dashboard_spec.pages:
            for visual in page.visuals:
                if visual.type not in allowed:
                    warnings.append(
                        Issue(
                            code="VTYPE",
                            severity="warning",
                            message=f"Type visuel non standard: {visual.type}",
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
