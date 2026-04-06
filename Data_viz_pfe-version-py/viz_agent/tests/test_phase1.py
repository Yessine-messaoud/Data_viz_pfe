from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry
from viz_agent.phase1_parser.dashboard_zone_mapper import extract_dashboard_worksheets
from viz_agent.phase1_parser.tableau_parser import TableauParser
from viz_agent.phase1_parser.visual_type_mapper import infer_logical_visual_type, infer_rdl_visual_type


def test_extract_dashboard_worksheets() -> None:
    xml = etree.fromstring(
        """
        <dashboard name='Sales Overview'>
          <zones>
            <zone type='sheet' name='SO_KPIs'/>
            <zone type='sheet' name='SO_TopCustomers'/>
            <zone type='layout' name='Container'/>
          </zones>
        </dashboard>
        """
    )

    worksheets = extract_dashboard_worksheets(xml)
    assert worksheets == ["SO_KPIs", "SO_TopCustomers"]


def test_infer_rdl_visual_type() -> None:
  assert infer_rdl_visual_type("SO_KPIs", "Text") == "Textbox"
  assert infer_rdl_visual_type("SalesbyCountry", "Map") == "Map"
  assert infer_rdl_visual_type("Unknown", "Line") == "LineChart"
  assert infer_rdl_visual_type("Treemap", "Treemap") == "TreeMap"


def test_infer_logical_visual_type() -> None:
    assert infer_logical_visual_type("Sales per country", "Bar") == "bar"
    assert infer_logical_visual_type("Feuille 3", "Treemap") == "treemap"
    assert infer_logical_visual_type("SO_KPIs", "Text") == "kpi"


def test_tableau_parser_reads_minimal_twbx(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <datasources>
        <datasource name='sales_data' caption='Sales'>
          <connection class='sqlserver'/>
        </datasource>
      </datasources>
      <worksheets>
        <worksheet name='SO_KPIs'>
          <mark class='Text'/>
          <datasource name='sales_data'/>
        </worksheet>
      </worksheets>
      <dashboards>
        <dashboard name='Sales Overview'>
          <zone type='sheet' name='SO_KPIs'/>
        </dashboard>
      </dashboards>
      <column name='[Calculation_1]' formula='SUM([Sales Amount])'/>
      <parameter name='pCountry' datatype='string' value='FR'/>
      <filter column='[Country]' op='=' value='FR'/>
      <preferences>
        <color-palette name='default'><color value='#123456'/></color-palette>
      </preferences>
    </workbook>
    """

    twbx_path = tmp_path / "sample.twbx"
    with zipfile.ZipFile(twb_path := twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parser = TableauParser()
    parsed = parser.parse(str(twb_path), DataSourceRegistry())

    assert len(parsed.worksheets) == 1
    assert parsed.worksheets[0].name == "SO_KPIs"
    assert len(parsed.dashboards) == 1
    assert parsed.dashboards[0].worksheets == ["SO_KPIs"]
    assert len(parsed.calculated_fields) == 1
    assert len(parsed.parameters) == 1
    assert len(parsed.filters) == 1
    assert parsed.worksheets[0].visual_encoding.x is None
    assert parsed.worksheets[0].confidence.overall >= 0.0
    assert parsed.visual_encoding["SO_KPIs"].y is None


def test_tableau_parser_extracts_worksheet_title() -> None:
    xml = etree.fromstring(
        """
        <workbook>
          <worksheet name='Sheet1'>
            <layout-options>
              <title><formatted-text><run>Sales per country</run></formatted-text></title>
            </layout-options>
            <table><panes><pane><mark class='Bar'/></pane></panes></table>
          </worksheet>
        </workbook>
        """
    )
    worksheets = TableauParser()._parse_worksheets(xml)
    assert len(worksheets) == 1
    assert worksheets[0].title == "Sales per country"


def test_tableau_parser_deduplicates_same_datasource_name(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <datasources>
        <datasource name='federated.x1' caption='Extract'>
          <connection class='sqlserver'/>
        </datasource>
        <datasource name='federated.x1' caption='Extract'>
          <connection class='sqlserver'/>
        </datasource>
      </datasources>
      <datasource-dependencies datasource='federated.x1'>
        <column name='[SalesAmount]' datatype='real' role='measure'/>
        <column name='[Country]' datatype='string' role='dimension'/>
      </datasource-dependencies>
      <datasource-dependencies datasource='federated.x1'>
        <column name='[Country]' datatype='string' role='dimension'/>
        <column name='[OrderQuantity]' datatype='integer' role='measure'/>
      </datasource-dependencies>
      <worksheets/>
      <dashboards/>
    </workbook>
    """

    twbx_path = tmp_path / "dup_ds.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = TableauParser().parse(str(twbx_path), DataSourceRegistry())
    assert len(parsed.datasources) == 1
    assert parsed.datasources[0].name == "federated.x1"
    col_names = [c.name for c in parsed.datasources[0].columns]
    assert col_names.count("Country") == 1
    assert "SalesAmount" in col_names
    assert "OrderQuantity" in col_names


def test_tableau_parser_decodes_federated_nk_filter_column(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <datasources>
        <datasource name='federated.x1' caption='Extract'>
          <connection class='sqlserver'/>
        </datasource>
      </datasources>
      <worksheets/>
      <dashboards/>
      <filter column='[federated.x1].[none:SalesTerritoryCountry:nk]' op='=' value='France'/>
    </workbook>
    """
    twbx_path = tmp_path / "filter_decode.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = TableauParser().parse(str(twbx_path), DataSourceRegistry())
    assert len(parsed.filters) == 1
    assert parsed.filters[0].field == "SalesTerritoryCountry"
    assert parsed.filters[0].column == "SalesTerritoryCountry"


def test_tableau_parser_infers_bar_from_automatic_rows_cols(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <worksheets>
        <worksheet name='W1'>
          <table>
            <view>
              <rows>[federated.x1].[sum:TaxAmt:qk]</rows>
              <cols>[federated.x1].[none:SalesTerritoryCountry:nk]</cols>
            </view>
            <panes><pane><mark class='Automatic'/></pane></panes>
          </table>
        </worksheet>
      </worksheets>
    </workbook>
    """
    twbx_path = tmp_path / "auto_bar.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = TableauParser().parse(str(twbx_path), DataSourceRegistry())
    assert len(parsed.worksheets) == 1
    assert parsed.worksheets[0].mark_type == "Bar"
    assert parsed.worksheets[0].confidence.visual >= 0.5


def test_tableau_parser_infers_treemap_from_automatic_encodings(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <worksheets>
        <worksheet name='W1'>
          <table>
            <panes>
              <pane>
                <mark class='Automatic'/>
                <encodings>
                  <size column='[federated.x1].[sum:OrderQuantity:qk]'/>
                  <color column='[federated.x1].[sum:OrderQuantity:qk]'/>
                  <text column='[federated.x1].[none:SalesTerritoryCountry:nk]'/>
                </encodings>
              </pane>
            </panes>
          </table>
        </worksheet>
      </worksheets>
    </workbook>
    """
    twbx_path = tmp_path / "auto_treemap.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = TableauParser().parse(str(twbx_path), DataSourceRegistry())
    assert len(parsed.worksheets) == 1
    assert parsed.worksheets[0].mark_type == "Treemap"
    assert parsed.worksheets[0].visual_encoding.color == "OrderQuantity"
    assert parsed.worksheets[0].semantic_hints
    assert parsed.worksheets[0].confidence.encoding > 0


def test_phase1_keeps_color_empty_when_only_size_exists(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <worksheets>
        <worksheet name='W_size_only'>
          <table>
            <panes>
              <pane>
                <mark class='Automatic'/>
                <encodings>
                  <size column='[federated.x1].[sum:OrderQuantity:qk]'/>
                  <text column='[federated.x1].[none:SalesTerritoryCountry:nk]'/>
                </encodings>
              </pane>
            </panes>
          </table>
        </worksheet>
      </worksheets>
    </workbook>
    """
    twbx_path = tmp_path / "size_without_color.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = TableauParser().parse(str(twbx_path), DataSourceRegistry())
    assert len(parsed.worksheets) == 1
    ws = parsed.worksheets[0]
    assert ws.visual_encoding.color in (None, "")
    assert ws.visual_encoding.size == "OrderQuantity"


def test_tableau_parser_extracts_tableau_join_relationships(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <datasources>
        <datasource name='federated.a' caption='Sales'>
          <connection class='sqlserver'>
            <relation type='join' join='left'>
              <relation type='table' table='federated.a'/>
              <relation type='table' table='federated.b'/>
              <clause expression='[federated.a].[CustomerKey] = [federated.b].[CustomerKey]'/>
            </relation>
          </connection>
        </datasource>
      </datasources>
      <worksheets/>
      <dashboards/>
    </workbook>
    """
    twbx_path = tmp_path / "relations.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = TableauParser().parse(str(twbx_path), DataSourceRegistry())
    assert len(parsed.tableau_relationships) == 1
    rel = parsed.tableau_relationships[0]
    assert rel["left_table"] == "federated.a"
    assert rel["right_table"] == "federated.b"
    assert rel["left_col"] == "CustomerKey"
    assert rel["right_col"] == "CustomerKey"
    assert rel["type"] == "LEFT"
