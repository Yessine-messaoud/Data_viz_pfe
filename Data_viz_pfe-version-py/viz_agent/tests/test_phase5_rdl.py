from __future__ import annotations

from unittest.mock import MagicMock

from viz_agent.models.abstract_spec import (
    AbstractSpec,
    ColumnDef,
    ColumnRef,
    DashboardPage,
    DashboardSpec,
    DataBinding,
    DataLineageSpec,
    Measure,
    MeasureRef,
    SemanticModel,
    TableRef,
    VisualSpec,
)
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
from viz_agent.phase5_rdl.rdl_layout_builder import RDLLayoutBuilder
from viz_agent.phase5_rdl.rdl_validator import RDLValidator
from viz_agent.phase4_transform.rdl_dataset_mapper import RDLDataset, RDLField


def test_rdl_layout_positions_do_not_overlap() -> None:
    builder = RDLLayoutBuilder()
    visuals = [
        VisualSpec(
            id=f"v{i}",
            source_worksheet=f"ws{i}",
            type="tablix",
            title=f"Visual {i}",
            data_binding=DataBinding(),
        )
        for i in range(4)
    ]

    dashboard = MagicMock()
    dashboard.width = 1200
    dashboard.height = 800

    layout = builder.compute_layout(dashboard, visuals)
    rects = list(layout.values())

    assert len(rects) == 4
    for i, r1 in enumerate(rects):
        for j, r2 in enumerate(rects):
            if i != j and abs(r1.top - r2.top) < 0.01:
                assert r1.left + r1.width <= r2.left + 0.01 or r2.left + r2.width <= r1.left + 0.01


def test_rdl_validator_catches_missing_dataset() -> None:
    minimal_rdl = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Report xmlns=\"http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition\">
  <DataSources><DataSource Name=\"ds1\"><ConnectionProperties>
    <DataProvider>SQL</DataProvider>
    <ConnectString>Server=localhost</ConnectString>
  </ConnectionProperties></DataSource></DataSources>
    <ReportSections>
        <ReportSection>
            <Body><ReportItems/></Body>
            <Page><PageHeight>8.5in</PageHeight><PageWidth>11in</PageWidth></Page>
        </ReportSection>
    </ReportSections>
</Report>"""

    report = RDLValidator().validate(minimal_rdl)
    errors = [e.code for e in report.errors]
    assert "R_STRUCT" in errors


def test_rdl_validator_accepts_valid_rdl() -> None:
    valid_rdl = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Report xmlns=\"http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition\">
  <DataSources><DataSource Name=\"ds1\"><ConnectionProperties>
    <DataProvider>SQL</DataProvider>
    <ConnectString>Server=localhost</ConnectString>
  </ConnectionProperties></DataSource></DataSources>
  <DataSets><DataSet Name=\"sales\">
    <Query><DataSourceName>ds1</DataSourceName>
    <CommandText>SELECT * FROM sales</CommandText></Query>
  </DataSet></DataSets>
    <ReportSections>
        <ReportSection>
            <Body><ReportItems/></Body>
            <Page><PageHeight>8.5in</PageHeight><PageWidth>11in</PageWidth></Page>
        </ReportSection>
    </ReportSections>
</Report>"""

    report = RDLValidator().validate(valid_rdl)
    assert report.can_proceed, f"Erreurs: {[e.message for e in report.errors]}"


def test_rdl_generator_builds_required_sections() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT * FROM sales_data",
        connection_ref="DataSource1",
        fields=[RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Float")],
    )

    visual = VisualSpec(
        id="SO_Sales",
        source_worksheet="SO_Sales",
        type="chart",
        title="Sales",
        data_binding=DataBinding(axes={"y": ColumnRef(table="sales_data", column="SalesAmount")}),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=[visual])]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesAmount")])]),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {
        "Sales Overview": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)
    }

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert "<DataSources>" in xml
    assert "<DataSets>" in xml
    assert "<Body>" in xml
    assert "<Page>" in xml


def test_rdl_generator_adds_fallback_item_when_no_visuals() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT * FROM sales_data",
        connection_ref="DataSource1",
        fields=[RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Float")],
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=[])]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesAmount")])]),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": {}}

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert "<ReportItems>" in xml
    assert "<Textbox Name=\"tbNoVisuals\">" in xml


def test_rdl_generator_resolves_measure_label_and_sets_decimal_for_sum_fields() -> None:
    dataset = RDLDataset(
        name="('Extract', 'Extract')",
        query="SELECT * FROM ('Extract', 'Extract')",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="TotalSales", data_field="TotalSales", rdl_type="String"),
            RDLField(name="TotalTax", data_field="TotalTax", rdl_type="String"),
            RDLField(name="TotalFreight", data_field="TotalFreight", rdl_type="String"),
            RDLField(name="TotalQuantity", data_field="TotalQuantity", rdl_type="String"),
            RDLField(name="OrderCount", data_field="OrderCount", rdl_type="String"),
        ],
    )

    visual = VisualSpec(
        id="Ventes_par_pays",
        source_worksheet="Ventes par pays",
        type="chart",
        title="Ventes par pays",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="('Extract', 'Extract')", column="Country"),
                "y": MeasureRef(name="Ventes Totales"),
            },
            measures=[MeasureRef(name="Ventes Totales")],
        ),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Ventes", visuals=[visual])]),
        semantic_model=SemanticModel(
            entities=[
                TableRef(
                    id="t1",
                    name="('Extract', 'Extract')",
                    columns=[
                        ColumnDef(name="Country", pbi_type="text", role="dimension"),
                        ColumnDef(name="TotalSales", pbi_type="text", role="measure", label="Ventes Totales"),
                    ],
                )
            ],
            measures=[
                Measure(
                    name="Ventes Totales",
                    expression="SUM(('Extract', 'Extract').TotalSales)",
                    tableau_expression="TotalSales",
                )
            ],
            fact_table="('Extract', 'Extract')",
        ),
        data_lineage=DataLineageSpec(
            tables=[
                TableRef(
                    id="t1",
                    name="('Extract', 'Extract')",
                    columns=[ColumnDef(name="Country"), ColumnDef(name="TotalSales")],
                )
            ]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Ventes": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert "<Y>=Sum(Fields!TotalSales.Value)</Y>" in xml
    assert "<Group Name=\"grp_Country\">" in xml
    assert "<GroupExpression>=Fields!Country.Value</GroupExpression>" in xml
    assert "<Field Name=\"TotalSales\">" in xml and "<rd:TypeName>Decimal</rd:TypeName>" in xml
    assert "<Field Name=\"OrderCount\">" in xml and "<rd:TypeName>Integer</rd:TypeName>" in xml
