from __future__ import annotations

import zipfile
from pathlib import Path

from viz_agent.phase1_parser.agent.deterministic_parser import DeterministicParser


def test_deterministic_parser_parses_rdl(tmp_path: Path) -> None:
    rdl_content = """<?xml version='1.0' encoding='utf-8'?>
    <Report xmlns='http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition'>
      <DataSets>
        <DataSet Name='SalesData'>
          <Query>
            <DataSourceName>DataSource1</DataSourceName>
            <CommandText>SELECT * FROM Sales</CommandText>
          </Query>
        </DataSet>
      </DataSets>
      <ReportSections>
        <ReportSection>
          <Body>
            <ReportItems>
              <Tablix Name='SalesTable'>
                <DataSetName>SalesData</DataSetName>
              </Tablix>
            </ReportItems>
          </Body>
        </ReportSection>
      </ReportSections>
    </Report>
    """

    rdl_path = tmp_path / "sample.rdl"
    rdl_path.write_text(rdl_content, encoding="utf-8")

    parsed = DeterministicParser().parse(str(rdl_path), metadata={})
    assert parsed["source_format"] == "rdl"
    assert parsed["dashboards"]
    assert parsed["visuals"]
    assert parsed["bindings"]


def test_deterministic_parser_parses_twbx(tmp_path: Path) -> None:
    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <worksheets>
        <worksheet name='Sheet1'><mark class='Bar'/></worksheet>
      </worksheets>
      <dashboards>
        <dashboard name='Main'>
          <zone type='sheet' name='Sheet1'/>
        </dashboard>
      </dashboards>
    </workbook>
    """
    twbx_path = tmp_path / "sample.twbx"
    with zipfile.ZipFile(twbx_path, "w") as archive:
        archive.writestr("workbook.twb", twb_content)

    parsed = DeterministicParser().parse(str(twbx_path), metadata={})
    assert parsed["source_format"] == "twb"
    assert parsed["dashboards"][0]["name"] == "Main"
    assert parsed["visuals"][0]["name"] == "Sheet1"
