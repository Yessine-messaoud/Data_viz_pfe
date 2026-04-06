from __future__ import annotations

from viz_agent.models.abstract_spec import (
    ColumnDef,
    ColumnRef,
    DataLineageSpec,
    DataSource,
    Filter,
    ParsedWorkbook,
    SemanticModel,
    TableRef,
    TableauDashboard,
    Worksheet,
)
from viz_agent.phase3_spec.abstract_spec_builder import AbstractSpecBuilder
from viz_agent.phase1_parser.visual_type_mapper import resolve_visual_mapping
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
    visuals = spec.dashboard_spec.pages[0].visuals
    assert all(v.type != "chart" for v in visuals)
    assert visuals[0].type == "kpi"
    assert visuals[0].rdl_type == "Textbox"
    assert visuals[1].type == "line"
    assert visuals[1].rdl_type == "LineChart"


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


def test_dashboard_spec_factory_deduplicates_global_filters() -> None:
    workbook = _build_workbook()
    workbook.filters = [
        Filter(field="SalesTerritoryCountry", operator="=", value="France", column="SalesTerritoryCountry"),
        Filter(field="SalesTerritoryCountry", operator="=", value="France", column="SalesTerritoryCountry"),
        Filter(field="ModelName", operator="=", value="Road-150", column="ModelName"),
    ]
    semantic_model = SemanticModel(fact_table="sales_data", grain="row")
    lineage = DataLineageSpec(
        tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="Sales Amount")])],
        joins=[],
    )

    spec = AbstractSpecBuilder.build(workbook, intent=None, semantic_model=semantic_model, lineage=lineage)
    assert len(spec.dashboard_spec.global_filters) == 2
    fields = [f.field for f in spec.dashboard_spec.global_filters]
    assert "SalesTerritoryCountry" in fields
    assert "ModelName" in fields


def test_visual_mapper_resolves_generic_chart_to_explicit_business_type() -> None:
    class _Encoding:
        x = "Country"
        y = "SalesAmount"
        color = None
        size = None
        detail = None

        def model_dump(self):
            return {
                "x": self.x,
                "y": self.y,
                "color": self.color,
                "size": self.size,
                "detail": self.detail,
            }

    resolved = resolve_visual_mapping("Sales by Country", mark_type="chart", encoding=_Encoding())
    assert resolved.logical_type == "bar"
    assert resolved.rdl_type == "ColumnChart"
    assert resolved.warning != ""


def test_abstract_spec_validator_flags_generic_rdl_type_chart() -> None:
    workbook = _build_workbook()
    semantic_model = SemanticModel(fact_table="sales_data", grain="row")
    lineage = DataLineageSpec(
        tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="Sales Amount")])],
        joins=[],
    )

    spec = AbstractSpecBuilder.build(workbook, intent=None, semantic_model=semantic_model, lineage=lineage)
    spec.rdl_datasets = [{"name": "sales_data"}]
    spec.dashboard_spec.pages[0].visuals[0].type = "bar"
    spec.dashboard_spec.pages[0].visuals[0].rdl_type = "chart"

    report = AbstractSpecValidator().validate(spec)
    error_codes = [issue.code for issue in report.errors]
    assert "VTYPE_GENERIC" in error_codes


def test_abstract_spec_validator_blocks_chart_with_dimension_on_y_axis() -> None:
    workbook = _build_workbook()
    semantic_model = SemanticModel(
        fact_table="sales_data",
        grain="row",
        entities=[
            TableRef(
                id="t1",
                name="sales_data",
                columns=[
                    ColumnDef(name="Country", role="dimension", pbi_type="text"),
                    ColumnDef(name="SalesAmount", role="measure", pbi_type="decimal"),
                ],
            )
        ],
    )
    lineage = DataLineageSpec(
        tables=[
            TableRef(
                id="t1",
                name="sales_data",
                columns=[ColumnDef(name="Country"), ColumnDef(name="SalesAmount")],
            )
        ],
        joins=[],
    )

    spec = AbstractSpecBuilder.build(workbook, intent=None, semantic_model=semantic_model, lineage=lineage)
    spec.rdl_datasets = [{"name": "sales_data"}]
    visual = spec.dashboard_spec.pages[0].visuals[0]
    visual.type = "bar"
    visual.rdl_type = "ColumnChart"
    visual.data_binding.axes = {
        "x": ColumnRef(table="sales_data", column="SalesAmount"),
        "y": ColumnRef(table="sales_data", column="Country"),
    }

    report = AbstractSpecValidator().validate(spec)
    error_codes = [issue.code for issue in report.errors]
    assert "SEM_BIND_Y_ROLE" in error_codes
