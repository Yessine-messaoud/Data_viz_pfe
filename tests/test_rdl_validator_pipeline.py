from __future__ import annotations

from viz_agent.phase5_rdl.rdl_validator_pipeline import RDLValidatorPipeline


NS_2016 = 'xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"'
NS_2008 = 'xmlns="http://schemas.microsoft.com/sqlserver/reporting/2008/01/reportdefinition"'


def _minimal_valid_rdl() -> str:
    return f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Report {NS_2016}>
  <DataSources>
    <DataSource Name=\"DS1\">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost;Initial Catalog=ReportData</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name=\"Sales\">
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT SalesAmount FROM Sales</CommandText>
      </Query>
      <Fields>
        <Field Name=\"SalesAmount\"><DataField>SalesAmount</DataField></Field>
      </Fields>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Tablix Name=\"Tab1\">
            <DataSetName>Sales</DataSetName>
            <TablixBody></TablixBody>
          </Tablix>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page>
        <PageHeight>11in</PageHeight>
        <PageWidth>8.5in</PageWidth>
        <TopMargin>0.25in</TopMargin>
        <BottomMargin>0.25in</BottomMargin>
        <LeftMargin>0.25in</LeftMargin>
        <RightMargin>0.25in</RightMargin>
      </Page>
    </ReportSection>
  </ReportSections>
</Report>"""


def test_pipeline_accepts_valid_rdl() -> None:
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(_minimal_valid_rdl(), auto_fix=True)
    assert report.can_proceed is True
    assert report.error_count == 0
    assert "<Report" in fixed


def test_pipeline_autofixes_namespace() -> None:
    bad = _minimal_valid_rdl().replace(NS_2016, NS_2008)
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "reporting/2016/01/reportdefinition" in fixed
    assert len(report.auto_fixes_applied) >= 1


def test_pipeline_flags_invalid_dataset_reference() -> None:
    bad = _minimal_valid_rdl().replace("<DataSetName>Sales</DataSetName>", "<DataSetName>UnknownDs</DataSetName>")
    pipeline = RDLValidatorPipeline()
    _, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is False
    assert any(i.code == "SEM001" for i in report.all_issues)
