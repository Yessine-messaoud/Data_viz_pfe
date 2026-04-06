from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from viz_agent.models.abstract_spec import (
    AbstractSpec,
    BuildLogEntry,
    ColumnRef,
    DashboardPage,
    DashboardSpec,
    DataBinding,
    Filter,
    MeasureRef,
    ParsedWorkbook,
    SemanticModel,
    VisualSpec,
)
from viz_agent.phase1_parser.dashboard_zone_mapper import infer_dashboard_name_from_worksheet
from viz_agent.phase3_spec.spec_correction import SpecCorrectionEngine
from viz_agent.phase3_spec.visual_decision_engine import VisualDecisionEngine


class DashboardSpecFactory:
    @staticmethod
    def _build_role_index(semantic_model: SemanticModel) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
        roles: dict[tuple[str, str], str] = {}
        role_by_column: dict[str, str] = {}
        collisions: set[str] = set()

        for entity in semantic_model.entities:
            table_name = getattr(entity, "name", "")
            for column in getattr(entity, "columns", []):
                role = str(column.role)
                column_name = str(column.name)
                roles[(str(table_name), column_name)] = role

                if column_name not in role_by_column:
                    role_by_column[column_name] = role
                elif role_by_column[column_name] != role:
                    collisions.add(column_name)

        for column_name in collisions:
            role_by_column.pop(column_name, None)

        return roles, role_by_column

    @staticmethod
    def _to_binding_ref(
        ref: ColumnRef,
        role_index: dict[tuple[str, str], str],
        role_by_column: dict[str, str],
    ) -> ColumnRef | MeasureRef:
        role = role_index.get((ref.table, ref.column), role_by_column.get(ref.column, "unknown"))
        if role == "measure":
            return MeasureRef(name=ref.column)
        return ref

    @staticmethod
    def _build_data_binding(
        ws,
        role_index: dict[tuple[str, str], str],
        role_by_column: dict[str, str],
    ) -> DataBinding:
        axes: dict[str, ColumnRef | MeasureRef] = {}
        mark_encodings = getattr(ws, "mark_encodings", {}) or {}

        if ws.cols_shelf:
            axes["x"] = DashboardSpecFactory._to_binding_ref(ws.cols_shelf[0], role_index, role_by_column)
        if ws.rows_shelf:
            axes["y"] = DashboardSpecFactory._to_binding_ref(ws.rows_shelf[0], role_index, role_by_column)
        color_ref = mark_encodings.get("color")
        size_ref = mark_encodings.get("size")
        detail_ref = mark_encodings.get("detail")

        if color_ref is not None:
            axes["color"] = DashboardSpecFactory._to_binding_ref(color_ref, role_index, role_by_column)
        elif ws.marks_shelf:
            axes["color"] = DashboardSpecFactory._to_binding_ref(ws.marks_shelf[0], role_index, role_by_column)

        if size_ref is not None:
            axes["size"] = DashboardSpecFactory._to_binding_ref(size_ref, role_index, role_by_column)
        elif len(ws.marks_shelf) >= 2:
            axes["size"] = DashboardSpecFactory._to_binding_ref(ws.marks_shelf[1], role_index, role_by_column)

        if detail_ref is not None:
            axes["detail"] = DashboardSpecFactory._to_binding_ref(detail_ref, role_index, role_by_column)
        elif len(ws.marks_shelf) >= 3:
            axes["detail"] = DashboardSpecFactory._to_binding_ref(ws.marks_shelf[2], role_index, role_by_column)

        measures: list[MeasureRef] = []
        for ref in ws.rows_shelf + ws.cols_shelf + ws.marks_shelf:
            role = role_index.get((ref.table, ref.column), role_by_column.get(ref.column, "unknown"))
            if role == "measure" and all(existing.name != ref.column for existing in measures):
                measures.append(MeasureRef(name=ref.column))

        return DataBinding(axes=axes, measures=measures)

    @staticmethod
    def _build_visuals(workbook: ParsedWorkbook, worksheet_names: list[str], semantic_model: SemanticModel) -> list[VisualSpec]:
        visuals, _, _ = DashboardSpecFactory._build_visuals_with_logs(workbook, worksheet_names, semantic_model)
        return visuals

    @staticmethod
    def _build_visuals_with_logs(
        workbook: ParsedWorkbook,
        worksheet_names: list[str],
        semantic_model: SemanticModel,
    ) -> tuple[list[VisualSpec], list[BuildLogEntry], list[str]]:
        visuals: list[VisualSpec] = []
        logs: list[BuildLogEntry] = []
        warnings: list[str] = []
        role_index, role_by_column = DashboardSpecFactory._build_role_index(semantic_model)
        decision_engine = VisualDecisionEngine()
        correction_engine = SpecCorrectionEngine()

        for worksheet_name in worksheet_names:
            ws = next((w for w in workbook.worksheets if w.name == worksheet_name), None)
            mark_type = ws.raw_mark_type if ws is not None and ws.raw_mark_type else (ws.mark_type if ws is not None else "Text")
            encoding = getattr(ws, "visual_encoding", None) if ws is not None else None
            confidence = getattr(ws, "confidence", None) if ws is not None else None
            visual_encoding = encoding or getattr(workbook, "visual_encoding", {}).get(worksheet_name) or None
            if visual_encoding is None:
                visual_encoding = ws.visual_encoding if ws is not None else None

            if visual_encoding is None:
                from viz_agent.models.abstract_spec import VisualEncoding

                visual_encoding = VisualEncoding()

            if confidence is None:
                from viz_agent.models.abstract_spec import ConfidenceScore

                confidence = ConfidenceScore()

            decision = decision_engine.decide(
                worksheet_name=worksheet_name,
                raw_mark_type=mark_type,
                visual_encoding=visual_encoding,
                confidence=confidence,
                semantic_model=semantic_model,
                workbook=workbook,
            )

            title = str(getattr(ws, "title", "") or "").strip() or worksheet_name
            visual = VisualSpec(
                id=worksheet_name,
                source_worksheet=worksheet_name,
                type=decision.final_visual_type,
                rdl_type=decision.rdl_type,
                title=title,
                data_binding=decision.validated_data_binding,
            )

            correction_result = correction_engine.correct(visual, semantic_model)
            final_visual = correction_result.visual_spec
            if correction_result.corrected:
                logs.append(
                    BuildLogEntry(
                        level="warning",
                        message=f"{worksheet_name}: {'; '.join(correction_result.corrections)}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
                warnings.extend(f"{worksheet_name}: {message}" for message in correction_result.corrections)
            if correction_result.issues:
                warnings.extend(f"{worksheet_name}: {issue}" for issue in correction_result.issues)
            if decision.warnings:
                warnings.extend(f"{worksheet_name}: {warning}" for warning in decision.warnings)
            if decision.corrections:
                logs.append(
                    BuildLogEntry(
                        level="info",
                        message=f"{worksheet_name}: {'; '.join(decision.corrections)}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                )
            visuals.append(final_visual)

            if ws is not None:
                ws.validation_warnings.extend(decision.warnings)

        return visuals, logs, warnings

    @staticmethod
    def from_workbook(workbook: ParsedWorkbook, semantic_model: SemanticModel) -> tuple[DashboardSpec, list[BuildLogEntry], list[str]]:
        pages: list[DashboardPage] = []
        build_logs: list[BuildLogEntry] = []
        warnings: list[str] = []

        if workbook.dashboards:
            for dashboard in workbook.dashboards:
                if dashboard.worksheets:
                    worksheet_names = dashboard.worksheets
                    pages_to_build = [(dashboard.name, worksheet_names)]
                else:
                    grouped: dict[str, list[str]] = {}
                    for worksheet in workbook.worksheets:
                        page_name = infer_dashboard_name_from_worksheet(worksheet.name) or dashboard.name
                        grouped.setdefault(page_name, []).append(worksheet.name)
                    pages_to_build = list(grouped.items()) if grouped else [(dashboard.name, [ws.name for ws in workbook.worksheets])]
                for page_name, worksheet_names in pages_to_build:
                    visuals, logs, page_warnings = DashboardSpecFactory._build_visuals_with_logs(workbook, worksheet_names, semantic_model)
                    build_logs.extend(logs)
                    warnings.extend(page_warnings)
                    pages.append(
                        DashboardPage(
                            id=page_name,
                            name=page_name,
                            visuals=visuals,
                        )
                    )
        else:
            fallback_worksheets = [ws.name for ws in workbook.worksheets]
            visuals, logs, page_warnings = DashboardSpecFactory._build_visuals_with_logs(workbook, fallback_worksheets, semantic_model)
            build_logs.extend(logs)
            warnings.extend(page_warnings)
            pages.append(
                DashboardPage(
                    id="default",
                    name="Default",
                    visuals=visuals,
                )
            )

        global_filters = [
            Filter(field=f.field, operator=f.operator, value=f.value, column=f.column)
            for f in workbook.filters
        ]
        deduped_filters: list[Filter] = []
        seen_filter_keys: set[tuple[str, str, str]] = set()
        for filt in global_filters:
            key = (
                str(filt.field or "").strip().lower(),
                str(filt.operator or "=").strip(),
                str(filt.value) if filt.value is not None else "",
            )
            if key in seen_filter_keys:
                continue
            seen_filter_keys.add(key)
            deduped_filters.append(filt)
        dashboard_spec = DashboardSpec(
            pages=pages,
            global_filters=deduped_filters,
            theme={"name": "tableau-imported", "build_log_count": len(build_logs), "warning_count": len(warnings)},
        )
        return dashboard_spec, build_logs, warnings


class AbstractSpecBuilder:
    @staticmethod
    def build(workbook: ParsedWorkbook, intent, semantic_model: SemanticModel, lineage) -> AbstractSpec:
        dashboard_spec, build_logs, warnings = DashboardSpecFactory.from_workbook(workbook, semantic_model)

        fingerprint_payload = (
            f"worksheets={len(workbook.worksheets)};"
            f"dashboards={len(workbook.dashboards)};"
            f"tables={len(lineage.tables)};"
            f"joins={len(lineage.joins)}"
        )

        return AbstractSpec(
            id=str(uuid.uuid4()),
            version="2.0.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_fingerprint=hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
            dashboard_spec=dashboard_spec,
            semantic_model=semantic_model,
            data_lineage=lineage,
            rdl_datasets=[],
            build_log=[
                BuildLogEntry(
                    level="info",
                    message="AbstractSpec v2 built with visual decision engine",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ),
                *build_logs,
            ],
            warnings=warnings,
        )
