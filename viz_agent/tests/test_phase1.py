from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from viz_agent.phase0_data.data_source_registry import DataSourceRegistry
from viz_agent.phase1_parser.dashboard_zone_mapper import extract_dashboard_worksheets
from viz_agent.phase1_parser.tableau_parser import TableauParser
from viz_agent.phase1_parser.visual_type_mapper import infer_rdl_visual_type


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
    assert infer_rdl_visual_type("SO_KPIs", "Text") == "textbox"
    assert infer_rdl_visual_type("SalesbyCountry", "Map") == "map"
    assert infer_rdl_visual_type("Unknown", "Line") == "chart"


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
