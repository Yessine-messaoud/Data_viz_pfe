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
            <TablixBody>
              <TablixColumns>
                <TablixColumn><Width>2in</Width></TablixColumn>
              </TablixColumns>
              <TablixRows>
                <TablixRow>
                  <Height>0.25in</Height>
                  <TablixCells>
                    <TablixCell>
                      <CellContents>
                        <Textbox Name=\"TB1\">
                          <Paragraphs>
                            <Paragraph>
                              <TextRuns>
                                <TextRun><Value>=Fields!SalesAmount.Value</Value></TextRun>
                              </TextRuns>
                            </Paragraph>
                          </Paragraphs>
                        </Textbox>
                      </CellContents>
                    </TablixCell>
                  </TablixCells>
                </TablixRow>
              </TablixRows>
            </TablixBody>
            <TablixColumnHierarchy><TablixMembers><TablixMember /></TablixMembers></TablixColumnHierarchy>
            <TablixRowHierarchy><TablixMembers><TablixMember /></TablixMembers></TablixRowHierarchy>
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


def test_pipeline_autofixes_missing_chartmember_label() -> None:
    bad = _minimal_valid_rdl().replace(
        "</ReportItems>",
        """
          <Chart Name=\"Chart1\">
            <Top>0.4in</Top>
            <Left>0in</Left>
            <Height>2in</Height>
            <Width>4in</Width>
            <DataSetName>Sales</DataSetName>
            <ChartCategoryHierarchy>
              <ChartMembers><ChartMember /></ChartMembers>
            </ChartCategoryHierarchy>
            <ChartSeriesHierarchy>
              <ChartMembers><ChartMember><Label>=\"S\"</Label></ChartMember></ChartMembers>
            </ChartSeriesHierarchy>
            <ChartData>
              <ChartSeriesCollection>
                <ChartSeries Name=\"Series1\">
                  <Type>Column</Type>
                  <ChartDataPoints>
                    <ChartDataPoint><ChartDataPointValues><Y>=Sum(Fields!SalesAmount.Value)</Y></ChartDataPointValues></ChartDataPoint>
                  </ChartDataPoints>
                  <ChartAreaName>Default</ChartAreaName>
                </ChartSeries>
              </ChartSeriesCollection>
            </ChartData>
            <ChartAreas><ChartArea Name=\"Default\" /></ChartAreas>
          </Chart>
        </ReportItems>
        """,
    )
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "added missing ChartMember labels" in " ".join(report.auto_fixes_applied)
    assert "<Label>" in fixed


def test_pipeline_autofixes_missing_tablix_row_hierarchy() -> None:
    bad = _minimal_valid_rdl().replace(
        "<TablixRowHierarchy><TablixMembers><TablixMember /></TablixMembers></TablixRowHierarchy>",
        "",
    )
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "normalized Tablix hierarchies" in " ".join(report.auto_fixes_applied)
    assert "<TablixRowHierarchy>" in fixed


def test_pipeline_autofixes_duplicate_report_item_names() -> None:
    bad = _minimal_valid_rdl().replace(
        "</ReportItems>",
        "<Textbox Name=\"TB1\"><Paragraphs><Paragraph><TextRuns><TextRun><Value>Dup</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox></ReportItems>",
    )
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "renamed duplicate ReportItem names" in " ".join(report.auto_fixes_applied)
    assert fixed.count('Name=\"TB1\"') == 1


def test_pipeline_autofixes_non_cls_parameter_name() -> None:
    bad = _minimal_valid_rdl().replace(
        "</DataSets>",
        """
  </DataSets>
  <ReportParameters>
    <ReportParameter Name="[federated.abc].[none:SalesTerritoryCountry:nk]">
      <DataType>String</DataType>
      <Prompt>Country</Prompt>
    </ReportParameter>
  </ReportParameters>
        """,
    )
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "normalized ReportParameter names to CLS identifiers" in " ".join(report.auto_fixes_applied)
    assert "[federated.abc].[none:SalesTerritoryCountry:nk]" not in fixed


def test_pipeline_autofixes_mismatched_parameter_layout() -> None:
    bad = _minimal_valid_rdl().replace(
        "</DataSets>",
        """
  </DataSets>
  <ReportParameters>
    <ReportParameter Name="P1"><DataType>String</DataType><Prompt>P1</Prompt></ReportParameter>
    <ReportParameter Name="P2"><DataType>String</DataType><Prompt>P2</Prompt></ReportParameter>
  </ReportParameters>
  <ReportParametersLayout>
    <GridLayoutDefinition>
      <NumberOfColumns>2</NumberOfColumns>
      <NumberOfRows>1</NumberOfRows>
      <CellDefinitions>
        <CellDefinition><ColumnIndex>0</ColumnIndex><RowIndex>0</RowIndex><ParameterName>P1</ParameterName></CellDefinition>
      </CellDefinitions>
    </GridLayoutDefinition>
  </ReportParametersLayout>
        """,
    )
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "removed inconsistent ReportParametersLayout" in " ".join(report.auto_fixes_applied)
    assert "<ReportParametersLayout>" not in fixed


def test_pipeline_autofixes_tablix_row_missing_tablixcells() -> None:
    bad = _minimal_valid_rdl().replace(
        "<TablixRows>",
        "<TablixRows><TablixRow><Height>0.25in</Height></TablixRow>",
    )
    bad = bad.replace(
        "<TablixRow>\n                  <Height>0.25in</Height>\n                  <TablixCells>",
        "<TablixRow><Height>0.25in</Height><TablixCells>",
    )
    pipeline = RDLValidatorPipeline()
    fixed, report = pipeline.validate_and_fix(bad, auto_fix=True)
    assert report.can_proceed is True
    assert "normalized TablixRow/TablixCells structure" in " ".join(report.auto_fixes_applied)
    assert "<TablixCells>" in fixed
