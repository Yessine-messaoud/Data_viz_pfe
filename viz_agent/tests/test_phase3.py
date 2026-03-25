from __future__ import annotations

from viz_agent.models.abstract_spec import (
    ColumnDef,
    DataLineageSpec,
    DataSource,
    ParsedWorkbook,
    SemanticModel,
    TableRef,
    TableauDashboard,
    Worksheet,
)
from viz_agent.phase3_spec.abstract_spec_builder import AbstractSpecBuilder
from viz_agent.phase3b_validator.abstract_spec_validator import AbstractSpecValidator


def _build_workbook() -> ParsedWorkbook:
    return ParsedWorkbook(
        worksheets=[
            Worksheet(name="SO_KPIs", mark_type="Text", datasource_name="sales_data"),
            Worksheet(name="SO_SalesbyMonth", mark_type="Line", datasource_name="sales_data"),
        ],
        datasources=[DataSource(name="sales_data", caption="Sales")],
        dashboards=[TableauDashboard(name="Sales Overview", worksheets=["SO_KPIs", "SO_SalesbyMonth"])],
        calculated_fields=[],
        parameters=[],
        filters=[],
        color_palettes=[],
        data_registry=None,
    )


def test_abstract_spec_builder_builds_pages_and_visuals() -> None:
    workbook = _build_workbook()
    semantic_model = SemanticModel(fact_table="sales_data", grain="row")
    lineage = DataLineageSpec(
        tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="Sales Amount")])],
        joins=[],
    )

    spec = AbstractSpecBuilder.build(workbook, intent=None, semantic_model=semantic_model, lineage=lineage)

    assert spec.version == "2.0.0"
    assert len(spec.dashboard_spec.pages) == 1
    assert spec.dashboard_spec.pages[0].name == "Sales Overview"
    assert len(spec.dashboard_spec.pages[0].visuals) == 2


def test_abstract_spec_validator_flags_missing_rdl_datasets() -> None:
    workbook = _build_workbook()
    semantic_model = SemanticModel(fact_table="sales_data", grain="row")
    lineage = DataLineageSpec(
        tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="Sales Amount")])],
        joins=[],
    )

    spec = AbstractSpecBuilder.build(workbook, intent=None, semantic_model=semantic_model, lineage=lineage)
    report = AbstractSpecValidator().validate(spec)

    error_codes = [issue.code for issue in report.errors]
    assert "R001" in error_codes
    assert report.can_proceed is False


def test_abstract_spec_validator_passes_when_datasets_present() -> None:
    workbook = _build_workbook()
    semantic_model = SemanticModel(fact_table="sales_data", grain="row")
    lineage = DataLineageSpec(
        tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="Sales Amount")], row_count=10)],
        joins=[],
    )

    spec = AbstractSpecBuilder.build(workbook, intent=None, semantic_model=semantic_model, lineage=lineage)
    spec.rdl_datasets = [{"name": "sales_data"}]

    report = AbstractSpecValidator().validate(spec)

    error_codes = [issue.code for issue in report.errors]
    assert "R001" not in error_codes
