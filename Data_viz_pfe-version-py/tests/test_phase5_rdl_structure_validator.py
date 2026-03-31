from viz_agent.phase5_rdl.rdl_structure_validator import RDLStructureValidator


def _minimal_valid_rdl() -> str:
    return (
        '<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition" '
        'xmlns:rd="http://schemas.microsoft.com/SQLServer/reporting/reportdesigner">'
        "<DataSources>"
        "<DataSource Name=\"DS1\"><ConnectionProperties><DataProvider>SQL</DataProvider><ConnectString>Data Source=.;</ConnectString></ConnectionProperties></DataSource>"
        "</DataSources>"
        "<DataSets>"
        "<DataSet Name=\"Main\">"
        "<Query><DataSourceName>DS1</DataSourceName><CommandText>SELECT 1 AS X</CommandText></Query>"
        "<Fields><Field Name=\"X\"><DataField>X</DataField><rd:TypeName>System.String</rd:TypeName></Field></Fields>"
        "</DataSet>"
        "</DataSets>"
        "<ReportSections><ReportSection>"
        "<Body><ReportItems><Textbox Name=\"TB1\"><CanGrow>true</CanGrow><KeepTogether>true</KeepTogether><Paragraphs><Paragraph><TextRuns><TextRun><Value>Hello</Value><Style /></TextRun></TextRuns><Style /></Paragraph></Paragraphs><rd:DefaultName>TB1</rd:DefaultName><Top>0in</Top><Left>0in</Left><Height>0.2in</Height><Width>2in</Width><Style /></Textbox></ReportItems><Height>2in</Height><Style /></Body>"
        "<Width>6in</Width>"
        "<Page><PageHeight>11in</PageHeight><PageWidth>8.5in</PageWidth><LeftMargin>1in</LeftMargin><RightMargin>1in</RightMargin><TopMargin>1in</TopMargin><BottomMargin>1in</BottomMargin><Style /></Page>"
        "</ReportSection></ReportSections>"
        "</Report>"
    )


def test_structure_validator_accepts_minimal_valid_rdl() -> None:
    report = RDLStructureValidator().validate(_minimal_valid_rdl())
    assert report.can_proceed is True
    assert report.errors == []


def test_structure_validator_rejects_markdown_fence() -> None:
    xml = "```xml\n" + _minimal_valid_rdl() + "\n```"
    report = RDLStructureValidator().validate(xml)
    assert report.can_proceed is False
    assert any(err.code == "RDL-STRUCT-001" for err in report.errors)


def test_structure_validator_rejects_duplicate_textbox_name() -> None:
    xml = _minimal_valid_rdl().replace(
        "</ReportItems>",
        "<Textbox Name=\"TB1\"><CanGrow>true</CanGrow><KeepTogether>true</KeepTogether><Paragraphs><Paragraph><TextRuns><TextRun><Value>Again</Value><Style /></TextRun></TextRuns><Style /></Paragraph></Paragraphs><rd:DefaultName>TB1</rd:DefaultName><Top>0.3in</Top><Left>0in</Left><Height>0.2in</Height><Width>2in</Width><Style /></Textbox></ReportItems>",
    )
    report = RDLStructureValidator().validate(xml)
    assert report.can_proceed is False
    assert any(err.code == "RDL-STRUCT-ITEMDUP" for err in report.errors)
