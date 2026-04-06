from __future__ import annotations

from unittest.mock import MagicMock
from lxml import etree

from viz_agent.models.abstract_spec import (
    AbstractSpec,
    ColumnDef,
    ColumnRef,
    DashboardPage,
    DashboardSpec,
    DataBinding,
    DataLineageSpec,
    Filter,
    Measure,
    MeasureRef,
    SemanticModel,
    TableRef,
    VisualSpec,
)
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
from viz_agent.phase5_rdl.rdl_layout_builder import RDLLayoutBuilder
from viz_agent.phase5_rdl.rdl_validator import RDLValidator
from viz_agent.phase5_rdl.rdl_visual_mapper import RDLVisualMapper
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

    assert (
        "<Y>=Sum(Fields!TotalSales.Value)</Y>" in xml
        or "<Y>=Sum(Fields!Ventes Totales.Value)</Y>" in xml
    )
    assert "<Group Name=\"grp_Country\">" in xml
    assert "<GroupExpression>=Fields!Country.Value</GroupExpression>" in xml
    assert "<Field Name=\"TotalSales\">" in xml and "<rd:TypeName>Decimal</rd:TypeName>" in xml
    assert "<Field Name=\"OrderCount\">" in xml and "<rd:TypeName>Integer</rd:TypeName>" in xml


def test_tablix_mapper_includes_required_hierarchies() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "1in"}

    dataset = RDLDataset(
        name="sales_data",
        query="SELECT * FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Float"),
        ],
    )
    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="tablix",
        title="Table",
        data_binding=DataBinding(),
    )

    tablix = RDLVisualMapper(use_llm=False).map_visual(visual, dataset, _Rect())
    assert tablix.find("TablixColumnHierarchy/TablixMembers/TablixMember") is not None
    assert tablix.find("TablixRowHierarchy/TablixMembers/TablixMember") is not None


def test_rdl_generator_propagates_global_filters_to_dataset_and_injects_datasource_metadata() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT Country, SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )

    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="chart",
        title="Sales by country",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="sales_data", column="Country"),
                "y": ColumnRef(table="sales_data", column="SalesAmount"),
            }
        ),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(
            pages=[DashboardPage(id="p1", name="Sales", visuals=[visual])],
            global_filters=[Filter(field="Country", operator="=", value="France")],
        ),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[
                TableRef(
                    id="t1",
                    name="sales_data",
                    columns=[ColumnDef(name="Country"), ColumnDef(name="SalesAmount")],
                )
            ]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert "<Description>" in xml and "Datasources:" in xml
    assert "<ReportParameters>" in xml
    assert "<FilterExpression>=Fields!Country.Value</FilterExpression>" in xml
    assert "<Operator>Equal</Operator>" in xml
    assert "=Parameters!Country.Value" in xml


def test_tablix_mapper_normalizes_rows_with_missing_tablixcells_from_llm() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "1in"}

    class _LLM:
        @staticmethod
        def chat_json(_system_prompt: str, _user_prompt: str):
            return {
                "rdl_xml": (
                    "<Tablix Name=\"BadTab\">"
                    "<DataSetName>Main</DataSetName>"
                    "<TablixBody>"
                    "<TablixColumns><TablixColumn><Width>1in</Width></TablixColumn></TablixColumns>"
                    "<TablixRows><TablixRow><Height>0.25in</Height></TablixRow></TablixRows>"
                    "</TablixBody>"
                    "</Tablix>"
                )
            }

    dataset = RDLDataset(
        name="sales_data",
        query="SELECT * FROM sales_data",
        connection_ref="DataSource1",
        fields=[RDLField(name="Country", data_field="Country", rdl_type="String")],
    )
    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="tablix",
        title="Table",
        data_binding=DataBinding(),
    )

    tablix = RDLVisualMapper(llm_client=_LLM(), use_llm=True).map_visual(visual, dataset, _Rect())
    first_row = tablix.find("TablixBody/TablixRows/TablixRow")
    assert first_row is not None
    assert first_row.find("TablixCells") is not None
    assert first_row.find("TablixCells/TablixCell/CellContents") is not None


def test_rdl_generator_deduplicates_dataset_fields_and_report_parameters() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT SalesTerritoryCountry FROM sales_data WHERE SalesTerritoryCountry = @SalesTerritoryCountry",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
        ],
    )

    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="tablix",
        title="Table",
        data_binding=DataBinding(),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(
            pages=[DashboardPage(id="p1", name="Sales Overview", visuals=[visual])],
            global_filters=[
                Filter(field="SalesTerritoryCountry", operator="=", value="France"),
                Filter(field="SalesTerritoryCountry", operator="=", value="Germany"),
            ],
        ),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesTerritoryCountry")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert xml.count('<Field Name="SalesTerritoryCountry">') == 1
    assert xml.count('<ReportParameter Name="SalesTerritoryCountry">') == 1


def test_rdl_generator_emits_report_parameters_from_global_filters_without_sql_params() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT SalesTerritoryCountry FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
        ],
    )

    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="tablix",
        title="Table",
        data_binding=DataBinding(),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(
            pages=[DashboardPage(id="p1", name="Sales Overview", visuals=[visual])],
            global_filters=[
                Filter(field="SalesTerritoryCountry", operator="=", value="France"),
            ],
        ),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesTerritoryCountry")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)

    assert "<ReportParameters>" in xml
    assert '<ReportParameter Name="SalesTerritoryCountry">' in xml


def test_rdl_generator_ensures_unique_report_item_names_for_multiple_tablix() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT Country, SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )

    visuals = [
        VisualSpec(id="Feuille_2", source_worksheet="Feuille 2", type="tablix", title="T1", data_binding=DataBinding()),
        VisualSpec(id="Feuille_3", source_worksheet="Feuille 3", type="tablix", title="T2", data_binding=DataBinding()),
    ]

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=visuals)]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="Country"), ColumnDef(name="SalesAmount")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": layout_builder.compute_layout(MagicMock(), visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)
    assert xml.count('Name="Header_SalesAmount"') == 0
    assert xml.count('Name="Feuille_2_Header_SalesAmount"') == 1
    assert xml.count('Name="Feuille_3_Header_SalesAmount"') == 1


def test_rdl_generator_preserves_chart_area_and_legend_references_for_multiple_charts() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT SalesTerritoryCountry, SalesAmount, TaxAmt FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
            RDLField(name="TaxAmt", data_field="TaxAmt", rdl_type="Decimal"),
        ],
    )

    visuals = [
        VisualSpec(
            id="Feuille_1",
            source_worksheet="Feuille 1",
            type="chart",
            title="Sales",
            data_binding=DataBinding(
                axes={
                    "x": ColumnRef(table="sales_data", column="SalesTerritoryCountry"),
                    "y": ColumnRef(table="sales_data", column="SalesAmount"),
                }
            ),
        ),
        VisualSpec(
            id="Feuille_2",
            source_worksheet="Feuille 2",
            type="chart",
            title="Tax",
            data_binding=DataBinding(
                axes={
                    "x": ColumnRef(table="sales_data", column="SalesTerritoryCountry"),
                    "y": ColumnRef(table="sales_data", column="TaxAmt"),
                }
            ),
        ),
    ]

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=visuals)]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesTerritoryCountry"), ColumnDef(name="SalesAmount"), ColumnDef(name="TaxAmt")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": layout_builder.compute_layout(MagicMock(), visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)
    root = etree.fromstring(xml.encode("utf-8"))

    ns = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}
    for chart in root.findall(".//r:Chart", namespaces=ns):
        area_ref = chart.findtext("r:ChartData/r:ChartSeriesCollection/r:ChartSeries/r:ChartAreaName", namespaces=ns)
        area_def = chart.find("r:ChartAreas/r:ChartArea", namespaces=ns)
        assert area_ref == area_def.get("Name")

        legend_ref = chart.findtext("r:ChartData/r:ChartSeriesCollection/r:ChartSeries/r:LegendName", namespaces=ns)
        legend_def = chart.find("r:ChartLegends/r:ChartLegend", namespaces=ns)
        assert legend_ref == legend_def.get("Name")


def test_rdl_generator_ensures_unique_group_names_across_charts() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT SalesTerritoryCountry, SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )

    visuals = [
        VisualSpec(
            id="Feuille_1",
            source_worksheet="Feuille 1",
            type="chart",
            title="Sales 1",
            data_binding=DataBinding(
                axes={
                    "x": ColumnRef(table="sales_data", column="SalesTerritoryCountry"),
                    "y": ColumnRef(table="sales_data", column="SalesAmount"),
                }
            ),
        ),
        VisualSpec(
            id="Feuille_2",
            source_worksheet="Feuille 2",
            type="chart",
            title="Sales 2",
            data_binding=DataBinding(
                axes={
                    "x": ColumnRef(table="sales_data", column="SalesTerritoryCountry"),
                    "y": ColumnRef(table="sales_data", column="SalesAmount"),
                }
            ),
        ),
        VisualSpec(
            id="Feuille_3",
            source_worksheet="Feuille 3",
            type="chart",
            title="Sales 3",
            data_binding=DataBinding(
                axes={
                    "x": ColumnRef(table="sales_data", column="SalesTerritoryCountry"),
                    "y": ColumnRef(table="sales_data", column="SalesAmount"),
                }
            ),
        ),
    ]

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=visuals)]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesTerritoryCountry"), ColumnDef(name="SalesAmount")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": layout_builder.compute_layout(MagicMock(), visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)
    root = etree.fromstring(xml.encode("utf-8"))
    ns = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}
    group_names = [
        str(group.get("Name", "")).strip().lower()
        for group in root.findall(".//r:Group", namespaces=ns)
        if str(group.get("Name", "")).strip()
    ]
    assert len(group_names) == len(set(group_names))


def test_chart_mapper_avoids_sum_on_dimension_text_field_for_y_axis() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "2in"}

    dataset = RDLDataset(
        name="europe_data",
        query="SELECT Region, Country, TotalRevenue FROM europe_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Region", data_field="Region", rdl_type="String"),
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="Total_Revenue", data_field="Total Revenue", rdl_type="String"),
        ],
    )

    visual = VisualSpec(
        id="VEurope",
        source_worksheet="WS_Europe",
        type="chart",
        title="Europe",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="europe_data", column="Region"),
                "y": ColumnRef(table="europe_data", column="Country"),
            }
        ),
    )

    chart = RDLVisualMapper(use_llm=False).map_visual(visual, dataset, _Rect())
    xml = etree.tostring(chart, encoding="unicode")
    assert "<Y>=Sum(Fields!Country.Value)</Y>" not in xml
    assert "<Y>=Sum(Fields!Total_Revenue.Value)</Y>" in xml


def test_rdl_generator_adds_fields_from_sql_alias_projection() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query=(
            "SELECT f.TaxAmt AS TaxAmount, "
            "f.OrderQuantity AS OrderQuantity, "
            "st.SalesTerritoryRegion AS SalesTerritoryRegion "
            "FROM dbo.FactInternetSales AS f "
            "INNER JOIN dbo.DimSalesTerritory AS st ON f.SalesTerritoryKey = st.SalesTerritoryKey"
        ),
        connection_ref="DataSource1",
        fields=[],
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=[])]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(tables=[TableRef(id="t1", name="sales_data", columns=[])]),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": {}}

    xml = RDLGenerator().generate(spec, layouts, pages)
    assert '<Field Name="TaxAmount">' in xml
    assert '<Field Name="OrderQuantity">' in xml
    assert '<Field Name="SalesTerritoryRegion">' in xml


def test_rdl_generator_maps_federated_logical_query_to_sql_server_query() -> None:
    dataset = RDLDataset(
        name="federated.abc123",
        query="SELECT * FROM federated.abc123",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
            RDLField(name="ModelName", data_field="ModelName", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
            RDLField(name="TaxAmt", data_field="TaxAmt", rdl_type="Decimal"),
            RDLField(name="OrderQuantity", data_field="OrderQuantity", rdl_type="Decimal"),
        ],
    )

    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="tablix",
        title="Table",
        data_binding=DataBinding(),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales Overview", visuals=[visual])]),
        semantic_model=SemanticModel(fact_table="federated.abc123"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="federated.abc123", columns=[ColumnDef(name="SalesAmount")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales Overview": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}

    xml = RDLGenerator().generate(spec, layouts, pages)
    assert "FROM dbo.FactInternetSales AS f" in xml
    assert "INNER JOIN dbo.DimSalesTerritory AS st" in xml
    assert "INNER JOIN dbo.DimProduct AS p" in xml


def test_chart_mapper_fallback_uses_existing_dataset_dimension_not_country_literal() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "2in"}

    dataset = RDLDataset(
        name="sales_data",
        query="SELECT * FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )
    visual = VisualSpec(
        id="VChart",
        source_worksheet="WS1",
        type="chart",
        title="Chart",
        data_binding=DataBinding(),  # no explicit x axis
    )

    chart = RDLVisualMapper(use_llm=False).map_visual(visual, dataset, _Rect())
    xml = etree.tostring(chart, encoding="unicode")
    assert "Fields!SalesTerritoryCountry.Value" in xml
    assert "Fields!Country.Value" not in xml


def test_chart_mapper_adds_title_axes_and_legend() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "2in"}

    dataset = RDLDataset(
        name="sales_data",
        query="SELECT * FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="SalesTerritoryCountry", data_field="SalesTerritoryCountry", rdl_type="String"),
            RDLField(name="TaxAmt", data_field="TaxAmt", rdl_type="Decimal"),
        ],
    )
    visual = VisualSpec(
        id="VChart",
        source_worksheet="WS1",
        type="chart",
        title="Tax per country",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="sales_data", column="SalesTerritoryCountry"),
                "y": ColumnRef(table="sales_data", column="TaxAmt"),
            }
        ),
    )

    chart = RDLVisualMapper(use_llm=False).map_visual(visual, dataset, _Rect())
    xml = etree.tostring(chart, encoding="unicode")
    assert "<ChartTitles>" in xml and "<ChartTitle " in xml and "<Caption>Tax per country</Caption>" in xml
    assert "ChartCategoryAxes" in xml and "Sales Territory Country" in xml
    assert "ChartValueAxes" in xml and "Tax Amt" in xml
    assert "ChartLegends" in xml and "LegendName" in xml
    assert 'Label>="Tax Amt"</Label>' in xml


def test_rdl_generator_adds_missing_visual_fields_to_dataset() -> None:
    dataset = RDLDataset(
        name="sales_data",
        query="SELECT SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal")],
    )

    visual = VisualSpec(
        id="V1",
        source_worksheet="WS1",
        type="chart",
        title="Sales by country",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="sales_data", column="Country"),
                "y": MeasureRef(name="SalesAmount"),
            },
            measures=[MeasureRef(name="SalesAmount")],
        ),
    )

    spec = AbstractSpec(
        dashboard_spec=DashboardSpec(pages=[DashboardPage(id="p1", name="Sales", visuals=[visual])]),
        semantic_model=SemanticModel(fact_table="sales_data"),
        data_lineage=DataLineageSpec(
            tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesAmount"), ColumnDef(name="Country")])]
        ),
        rdl_datasets=[dataset],
    )

    layout_builder = RDLLayoutBuilder()
    pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)
    layouts = {"Sales": layout_builder.compute_layout(MagicMock(), spec.dashboard_spec.pages[0].visuals)}
    xml = RDLGenerator().generate(spec, layouts, pages)

    assert '<Field Name="Country">' in xml


def test_chart_mapper_emits_explicit_series_type_and_pie_subtype() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "2in"}

    dataset = RDLDataset(
        name="sales_data",
        query="SELECT Country, SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )

    pie_visual = VisualSpec(
        id="VPie",
        source_worksheet="WSPie",
        type="pie",
        rdl_type="PieChart",
        title="Pie",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="sales_data", column="Country"),
                "y": MeasureRef(name="SalesAmount"),
            },
            measures=[MeasureRef(name="SalesAmount")],
        ),
    )

    chart = RDLVisualMapper(use_llm=False).map_visual(pie_visual, dataset, _Rect())
    xml = etree.tostring(chart, encoding="unicode")

    assert "<Type>Shape</Type>" in xml
    assert "<Subtype>Pie</Subtype>" in xml


def test_chart_mapper_propagates_color_encoding_to_series_grouping() -> None:
    class _Rect:
        width = 4.0

        @staticmethod
        def to_rdl():
            return {"Left": "0in", "Top": "0in", "Width": "4in", "Height": "2in"}

    dataset = RDLDataset(
        name="sales_data",
        query="SELECT Country, ProductCategory, SalesAmount FROM sales_data",
        connection_ref="DataSource1",
        fields=[
            RDLField(name="Country", data_field="Country", rdl_type="String"),
            RDLField(name="ProductCategory", data_field="ProductCategory", rdl_type="String"),
            RDLField(name="SalesAmount", data_field="SalesAmount", rdl_type="Decimal"),
        ],
    )

    visual = VisualSpec(
        id="VColor",
        source_worksheet="WSColor",
        type="bar",
        rdl_type="ColumnChart",
        title="Sales by country and category",
        data_binding=DataBinding(
            axes={
                "x": ColumnRef(table="sales_data", column="Country"),
                "y": MeasureRef(name="SalesAmount"),
                "color": ColumnRef(table="sales_data", column="ProductCategory"),
            },
            measures=[MeasureRef(name="SalesAmount")],
        ),
    )

    chart = RDLVisualMapper(use_llm=False).map_visual(visual, dataset, _Rect())
    xml = etree.tostring(chart, encoding="unicode")

    assert "Fields!ProductCategory.Value" in xml
    assert "grp_series_ProductCategory" in xml
