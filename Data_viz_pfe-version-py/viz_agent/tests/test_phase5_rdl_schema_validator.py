from __future__ import annotations

from lxml import etree

from viz_agent.phase5_rdl.rdl_schema_validator import RDLSchemaValidator


def test_schema_validator_rejects_tablix_missing_row_hierarchy() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="X"><DataField>X</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 1 AS X</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Tablix Name="T1">
            <DataSetName>Main</DataSetName>
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
                        <Textbox Name="TB1">
                          <Paragraphs><Paragraph><TextRuns><TextRun><Value>=Fields!X.Value</Value></TextRun></TextRuns></Paragraph></Paragraphs>
                        </Textbox>
                      </CellContents>
                    </TablixCell>
                  </TablixCells>
                </TablixRow>
              </TablixRows>
            </TablixBody>
            <TablixColumnHierarchy><TablixMembers><TablixMember /></TablixMembers></TablixColumnHierarchy>
          </Tablix>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page>
        <PageHeight>11in</PageHeight>
        <PageWidth>8.5in</PageWidth>
      </Page>
    </ReportSection>
  </ReportSections>
</Report>"""

    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code in {"S005", "S005e"} for issue in report.errors)


def test_schema_validator_rejects_duplicate_dataset_field_names() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="Country"><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
        <Field Name="Country"><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 'FR' AS Country</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body><ReportItems><Textbox Name="TB1"><Paragraphs><Paragraph><TextRuns><TextRun><Value>ok</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox></ReportItems><Height>2in</Height></Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code == "S003f" for issue in report.errors)


def test_schema_validator_rejects_non_cls_dataset_field_name() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="Item Type"><DataField>Item Type</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT [Item Type] FROM t</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body><ReportItems><Textbox Name="TB1"><Paragraphs><Paragraph><TextRuns><TextRun><Value>ok</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox></ReportItems><Height>2in</Height></Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code == "S003g" for issue in report.errors)


def test_schema_validator_rejects_duplicate_report_item_names() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="Country"><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 'FR' AS Country</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Textbox Name="TB1"><Paragraphs><Paragraph><TextRuns><TextRun><Value>1</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox>
          <Textbox Name="TB1"><Paragraphs><Paragraph><TextRuns><TextRun><Value>2</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code == "S009" for issue in report.errors)


def test_schema_validator_rejects_non_cls_parameter_name() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="Country"><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 'FR' AS Country</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportParameters>
    <ReportParameter Name="[federated.abc].[none:SalesTerritoryCountry:nk]">
      <DataType>String</DataType>
      <Prompt>Country</Prompt>
    </ReportParameter>
  </ReportParameters>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Textbox Name="TB1"><Paragraphs><Paragraph><TextRuns><TextRun><Value>1</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code == "S008d" for issue in report.errors)


def test_schema_validator_rejects_mismatched_parameter_layout() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="Country"><DataField>Country</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 'FR' AS Country</CommandText>
      </Query>
    </DataSet>
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
        <CellDefinition>
          <ColumnIndex>0</ColumnIndex>
          <RowIndex>0</RowIndex>
          <ParameterName>P1</ParameterName>
        </CellDefinition>
      </CellDefinitions>
    </GridLayoutDefinition>
  </ReportParametersLayout>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Textbox Name="TB1"><Paragraphs><Paragraph><TextRuns><TextRun><Value>1</Value></TextRun></TextRuns></Paragraph></Paragraphs></Textbox>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code == "S008e" for issue in report.errors)


def test_schema_validator_rejects_tablix_row_missing_tablixcells() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">
  <DataSources>
    <DataSource Name="DS1">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=localhost</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Main">
      <Fields>
        <Field Name="X"><DataField>X</DataField><rd:TypeName>String</rd:TypeName></Field>
      </Fields>
      <Query>
        <DataSourceName>DS1</DataSourceName>
        <CommandText>SELECT 1 AS X</CommandText>
      </Query>
    </DataSet>
  </DataSets>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Tablix Name="T1">
            <DataSetName>Main</DataSetName>
            <TablixBody>
              <TablixColumns><TablixColumn><Width>2in</Width></TablixColumn></TablixColumns>
              <TablixRows><TablixRow><Height>0.25in</Height></TablixRow></TablixRows>
            </TablixBody>
            <TablixColumnHierarchy><TablixMembers><TablixMember /></TablixMembers></TablixColumnHierarchy>
            <TablixRowHierarchy><TablixMembers><TablixMember /></TablixMembers></TablixRowHierarchy>
          </Tablix>
        </ReportItems>
        <Height>2in</Height>
      </Body>
      <Width>6in</Width>
      <Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth></Page>
    </ReportSection>
  </ReportSections>
</Report>"""
    root = etree.fromstring(xml.encode("utf-8"))
    report = RDLSchemaValidator().validate(root)
    assert not report.can_proceed
    assert any(issue.code == "S005f" for issue in report.errors)
