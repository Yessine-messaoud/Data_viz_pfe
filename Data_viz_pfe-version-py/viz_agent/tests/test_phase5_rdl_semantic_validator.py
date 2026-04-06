from __future__ import annotations

from lxml import etree

from viz_agent.phase5_rdl.rdl_semantic_validator import RDLSemanticValidator


def test_rdl_semantic_validator_blocks_numeric_category_dimension_on_chart() -> None:
    xml = """<?xml version='1.0' encoding='UTF-8'?>
<Report xmlns='http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition'
        xmlns:rd='http://schemas.microsoft.com/SQLServer/reporting/reportdesigner'>
  <DataSources>
    <DataSource Name='DS1'>
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name='Main'>
      <Fields>
        <Field Name='CountryCode'><DataField>CountryCode</DataField><rd:TypeName>Decimal</rd:TypeName></Field>
        <Field Name='SalesAmount'><DataField>SalesAmount</DataField><rd:TypeName>Decimal</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 1 AS CountryCode, 10 AS SalesAmount</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Chart Name='C1'>
            <DataSetName>Main</DataSetName>
            <ChartCategoryHierarchy>
              <ChartMembers>
                <ChartMember>
                  <Label>=Fields!CountryCode.Value</Label>
                </ChartMember>
              </ChartMembers>
            </ChartCategoryHierarchy>
            <ChartSeriesHierarchy>
              <ChartMembers><ChartMember><Label>="Sales"</Label></ChartMember></ChartMembers>
            </ChartSeriesHierarchy>
            <ChartData>
              <ChartSeriesCollection>
                <ChartSeries Name='Series1'>
                  <Type>Column</Type>
                  <ChartDataPoints>
                    <ChartDataPoint>
                      <ChartDataPointValues>
                        <Y>=Sum(Fields!SalesAmount.Value)</Y>
                      </ChartDataPointValues>
                    </ChartDataPoint>
                  </ChartDataPoints>
                </ChartSeries>
              </ChartSeriesCollection>
            </ChartData>
          </Chart>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>
"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSemanticValidator().validate(root)

    assert any(issue.code == "SEM010" for issue in report.errors)
    assert report.can_proceed is False
