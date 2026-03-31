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
from viz_agent.phase1_parser.visual_type_mapper import infer_rdl_visual_type


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

        if ws.cols_shelf:
            axes["x"] = DashboardSpecFactory._to_binding_ref(ws.cols_shelf[0], role_index, role_by_column)
        if ws.rows_shelf:
            axes["y"] = DashboardSpecFactory._to_binding_ref(ws.rows_shelf[0], role_index, role_by_column)

        measures: list[MeasureRef] = []
        for ref in ws.rows_shelf + ws.cols_shelf + ws.marks_shelf:
            role = role_index.get((ref.table, ref.column), role_by_column.get(ref.column, "unknown"))
            if role == "measure" and all(existing.name != ref.column for existing in measures):
                measures.append(MeasureRef(name=ref.column))

        return DataBinding(axes=axes, measures=measures)

    @staticmethod
    def _build_visuals(workbook: ParsedWorkbook, worksheet_names: list[str], semantic_model: SemanticModel) -> list[VisualSpec]:
        visuals: list[VisualSpec] = []
        role_index, role_by_column = DashboardSpecFactory._build_role_index(semantic_model)

        for worksheet_name in worksheet_names:
            ws = next((w for w in workbook.worksheets if w.name == worksheet_name), None)
            mark_type = ws.mark_type if ws is not None else "Text"
            data_binding = (
                DashboardSpecFactory._build_data_binding(ws, role_index, role_by_column)
                if ws is not None
                else DataBinding()
            )

            visuals.append(
                VisualSpec(
                    id=worksheet_name,
                    source_worksheet=worksheet_name,
                    type=infer_rdl_visual_type(worksheet_name, mark_type),
                    title=worksheet_name,
                    data_binding=data_binding,
                )
            )
        return visuals

    @staticmethod
    def from_workbook(workbook: ParsedWorkbook, semantic_model: SemanticModel) -> DashboardSpec:
        pages: list[DashboardPage] = []

        if workbook.dashboards:
            for dashboard in workbook.dashboards:
                worksheet_names = dashboard.worksheets or [ws.name for ws in workbook.worksheets]
                pages.append(
                    DashboardPage(
                        id=dashboard.name,
                        name=dashboard.name,
                        visuals=DashboardSpecFactory._build_visuals(workbook, worksheet_names, semantic_model),
                    )
                )
        else:
            fallback_worksheets = [ws.name for ws in workbook.worksheets]
            pages.append(
                DashboardPage(
                    id="default",
                    name="Default",
                    visuals=DashboardSpecFactory._build_visuals(workbook, fallback_worksheets, semantic_model),
                )
            )

        global_filters = [
            Filter(field=f.field, operator=f.operator, value=f.value, column=f.column)
            for f in workbook.filters
        ]
        return DashboardSpec(pages=pages, global_filters=global_filters, theme={"name": "tableau-imported"})


class AbstractSpecBuilder:
    @staticmethod
    def build(workbook: ParsedWorkbook, intent, semantic_model: SemanticModel, lineage) -> AbstractSpec:
        dashboard_spec = DashboardSpecFactory.from_workbook(workbook, semantic_model)

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
                    message="AbstractSpec v2 built",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            ],
            warnings=[],
        )
