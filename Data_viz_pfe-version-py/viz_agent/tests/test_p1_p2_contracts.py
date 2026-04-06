from __future__ import annotations

from lxml import etree

from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook, SemanticModel
from viz_agent.models.validation import Issue
from viz_agent.phase2_semantic.phase2_orchestrator import Phase2SemanticOrchestrator
from viz_agent.phase5_rdl.rdl_auto_fixer import RDLAutoFixer
from viz_agent.phase5_rdl.rdl_dataset_validator import RDLDatasetValidator


def test_phase2_orchestrator_run_with_result_success() -> None:
    orchestrator = Phase2SemanticOrchestrator()

    def _fake_run(_workbook, _intent=None):
        return (
            SemanticModel(fact_table="sales_data"),
            DataLineageSpec(tables=[]),
            {"orchestration": {"overall_confidence": 0.84, "selected_path": "fast"}},
        )

    orchestrator.run = _fake_run  # type: ignore[method-assign]

    semantic_model, lineage, artifacts, result = orchestrator.run_with_result(ParsedWorkbook(), {"type": "conversion"})

    assert semantic_model is not None
    assert lineage is not None
    assert isinstance(artifacts, dict)
    assert result.ok is True
    assert result.phase == "phase2_semantic"
    assert result.confidence == 0.84
    assert result.artifacts.get("path") == "fast"


def test_phase2_orchestrator_run_with_result_failure() -> None:
    orchestrator = Phase2SemanticOrchestrator()

    def _fake_run(_workbook, _intent=None):
        raise RuntimeError("semantic backend unavailable")

    orchestrator.run = _fake_run  # type: ignore[method-assign]

    semantic_model, lineage, artifacts, result = orchestrator.run_with_result(ParsedWorkbook(), {"type": "conversion"})

    assert semantic_model is None
    assert lineage is None
    assert artifacts == {}
    assert result.ok is False
    assert result.retry_hint != ""
    assert any("semantic backend unavailable" in msg for msg in result.errors)


def test_rendering_contract_blocks_missing_dataset_field_reference() -> None:
    xml = """<?xml version='1.0' encoding='UTF-8'?>
<Report xmlns='http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition'
        xmlns:rd='http://schemas.microsoft.com/SQLServer/reporting/reportdesigner'>
  <DataSources>
    <DataSource Name='DS1'><ConnectionProperties><DataProvider>SQL</DataProvider><ConnectString>localhost</ConnectString></ConnectionProperties></DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name='Main'>
      <Fields>
        <Field Name='Country'><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query><DataSourceName>DS1</DataSourceName><CommandText>SELECT Country FROM t</CommandText></Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Tablix Name='T1'>
            <DataSetName>Main</DataSetName>
            <TablixBody>
              <TablixColumns><TablixColumn><Width>2in</Width></TablixColumn></TablixColumns>
              <TablixRows>
                <TablixRow>
                  <Height>0.25in</Height>
                  <TablixCells>
                    <TablixCell>
                      <CellContents>
                        <Textbox Name='TB1'>
                          <Paragraphs><Paragraph><TextRuns><TextRun><Value>=Fields!MissingField.Value</Value></TextRun></TextRuns></Paragraph></Paragraphs>
                        </Textbox>
                      </CellContents>
                    </TablixCell>
                  </TablixCells>
                </TablixRow>
              </TablixRows>
            </TablixBody>
          </Tablix>
        </ReportItems>
      </Body>
    </ReportSection>
  </ReportSections>
</Report>
"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLDatasetValidator().validate_rendering_contract(root)
    assert report.can_proceed is False
    assert any(issue.code == "R103" for issue in report.errors)


def test_rendering_contract_blocks_chart_without_category() -> None:
    xml = """<?xml version='1.0' encoding='UTF-8'?>
<Report xmlns='http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition'
        xmlns:rd='http://schemas.microsoft.com/SQLServer/reporting/reportdesigner'>
  <DataSources>
    <DataSource Name='DS1'><ConnectionProperties><DataProvider>SQL</DataProvider><ConnectString>localhost</ConnectString></ConnectionProperties></DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name='Main'>
      <Fields>
        <Field Name='Country'><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
        <Field Name='SalesAmount'><DataField>SalesAmount</DataField><rd:TypeName>Decimal</rd:TypeName></Field>
      </Fields>
      <Query><DataSourceName>DS1</DataSourceName><CommandText>SELECT Country, SalesAmount FROM t</CommandText></Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Chart Name='C1'>
            <DataSetName>Main</DataSetName>
            <ChartSeriesHierarchy><ChartMembers><ChartMember><Label>="Sales"</Label></ChartMember></ChartMembers></ChartSeriesHierarchy>
            <ChartData>
              <ChartSeriesCollection>
                <ChartSeries Name='S1'>
                  <Type>Column</Type>
                  <ChartDataPoints>
                    <ChartDataPoint><ChartDataPointValues><Y>=Sum(Fields!SalesAmount.Value)</Y></ChartDataPointValues></ChartDataPoint>
                  </ChartDataPoints>
                </ChartSeries>
              </ChartSeriesCollection>
            </ChartData>
          </Chart>
        </ReportItems>
      </Body>
    </ReportSection>
  </ReportSections>
</Report>
"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLDatasetValidator().validate_rendering_contract(root)
    assert report.can_proceed is False
    assert any(issue.code == "R104" for issue in report.errors)


def test_auto_fixer_skips_destructive_code_x005() -> None:
    fixer = RDLAutoFixer()
    rdl = "<Report>\x01<Body/></Report>"
    fixed, logs = fixer.fix_all(
        rdl,
        [Issue(code="X005", severity="error", message="control char")],
    )
    assert fixed == rdl
    assert logs == []
