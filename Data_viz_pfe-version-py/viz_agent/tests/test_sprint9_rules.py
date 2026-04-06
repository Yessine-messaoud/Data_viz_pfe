from __future__ import annotations

from viz_agent.models.abstract_spec import (
    DataLineageSpec,
    ParsedWorkbook,
    SemanticModel,
    TableauDashboard,
    Worksheet,
)
from viz_agent.phase1_parser.visual_type_mapper import infer_rdl_visual_type
from viz_agent.phase3_spec.abstract_spec_builder import AbstractSpecBuilder


def test_prefix_mapping_builds_cd_pd_so_pages() -> None:
    workbook = ParsedWorkbook(
        worksheets=[
            Worksheet(name="CD_TopByCity", mark_type="Bar", datasource_name="sales_data"),
            Worksheet(name="PD_KPIs", mark_type="Text", datasource_name="sales_data"),
            Worksheet(name="SO_SalesProduct", mark_type="Bar", datasource_name="sales_data"),
        ],
        dashboards=[TableauDashboard(name="Any", worksheets=[])],
    )

    spec = AbstractSpecBuilder.build(
        workbook=workbook,
        intent={"action": "export_rdl"},
        semantic_model=SemanticModel(fact_table="sales_data"),
        lineage=DataLineageSpec(),
    )

    page_names = [page.name for page in spec.dashboard_spec.pages]
    assert page_names == ["Customer Details", "Product Details", "Sales Overview"]

    assert [v.source_worksheet for v in spec.dashboard_spec.pages[0].visuals] == ["CD_TopByCity"]
    assert [v.source_worksheet for v in spec.dashboard_spec.pages[1].visuals] == ["PD_KPIs"]
    assert [v.source_worksheet for v in spec.dashboard_spec.pages[2].visuals] == ["SO_SalesProduct"]


def test_kpi_is_mapped_to_textbox() -> None:
    assert infer_rdl_visual_type("SO_KPIs", "Text") == "Textbox"
    assert infer_rdl_visual_type("MyKPIWidget", "Bar") == "Textbox"
