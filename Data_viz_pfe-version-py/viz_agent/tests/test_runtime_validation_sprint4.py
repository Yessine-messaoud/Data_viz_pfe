from __future__ import annotations

from pathlib import Path

from viz_agent.orchestrator.modular_planner import PlannerAgent
from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.pipeline_context import PipelineContext
from viz_agent.orchestrator.runtime_error_normalizer import normalize_runtime_error
from viz_agent.orchestrator.runtime_validation import RDLRuntimeValidator


def _valid_rdl_payload() -> str:
    return """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Report xmlns=\"http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition\">
  <AutoRefresh>0</AutoRefresh>
  <DataSources>
    <DataSource Name=\"DataSource1\">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=.;Initial Catalog=master</ConnectString>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>
          <Textbox Name=\"Textbox1\">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>Hello</Value>
                    <Style/>
                  </TextRun>
                </TextRuns>
                <Style/>
              </Paragraph>
            </Paragraphs>
            <Top>0in</Top>
            <Left>0in</Left>
            <Height>0.2in</Height>
            <Width>2in</Width>
            <Style/>
          </Textbox>
        </ReportItems>
        <Height>2in</Height>
        <Style/>
      </Body>
      <Width>6.5in</Width>
      <Page>
        <PageHeight>11in</PageHeight>
        <PageWidth>8.5in</PageWidth>
        <LeftMargin>1in</LeftMargin>
        <RightMargin>1in</RightMargin>
        <TopMargin>1in</TopMargin>
        <BottomMargin>1in</BottomMargin>
        <Style/>
      </Page>
    </ReportSection>
  </ReportSections>
  <Language>en-US</Language>
</Report>
"""


def _spec_output() -> dict:
    return {
        "abstract_spec": {
            "dashboard_spec": {
                "pages": [
                    {
                        "visuals": [
                            {
                                "type": "columnchart",
                                "data_binding": {"axes": {"x": "Category", "y": "Sales"}},
                            }
                        ]
                    }
                ]
            }
        }
    }


class _FakeAgent:
    def __init__(self, name: str, sequence: list[PhaseAgentResult]):
        self.name = name
        self._sequence = list(sequence)
        self.calls = 0

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        idx = min(self.calls, len(self._sequence) - 1)
        self.calls += 1
        result = self._sequence[idx].normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        return result


def test_runtime_error_normalizer_maps_schema_error() -> None:
    err = normalize_runtime_error("Element 'Textbox' is invalid")
    assert err["type"] == "schema_error"
    assert err["location"] == "Textbox"
    assert err["severity"] == "P1"


def test_runtime_validator_open_success(tmp_path) -> None:
    rdl_path = tmp_path / "sample.rdl"
    rdl_path.write_text(_valid_rdl_payload(), encoding="utf-8")

    validator = RDLRuntimeValidator(enable_schema_validation=False)
    result = validator.validate_file(rdl_path)

    assert result["status"] == "success"
    assert result["errors"] == []
    assert result["confidence"] > 0.8


def test_planner_routes_runtime_schema_error_to_rdl_agent(tmp_path) -> None:
    rdl_path = Path(tmp_path) / "out.rdl"
    rdl_path.write_text(_valid_rdl_payload(), encoding="utf-8")

    parsing = _FakeAgent("parsing", [PhaseAgentResult(status="success", confidence=0.9, output={"parsed_structure": {"worksheets": [{"name": "ws1"}]}})])
    semantic = _FakeAgent("semantic_reasoning", [PhaseAgentResult(status="success", confidence=0.9, output={"semantic_graph": {"columns": []}})])
    spec = _FakeAgent("specification", [PhaseAgentResult(status="success", confidence=0.9, output=_spec_output())])
    transform = _FakeAgent("transformation", [PhaseAgentResult(status="success", confidence=0.9, output={"tool_model": {"datasets": []}})])
    export = _FakeAgent("export", [PhaseAgentResult(status="success", confidence=0.9, output={"export_result": {"validation": {"is_valid": True}, "content_bytes": 120, "rdl_path": str(rdl_path)}})])
    runtime = _FakeAgent(
        "runtime_validation",
        [
            PhaseAgentResult(
                status="error",
                confidence=0.2,
                output={
                    "runtime_validation": {
                        "status": "failure",
                        "errors": [
                            {
                                "type": "schema_error",
                                "message": "Element 'Textbox' is invalid",
                                "location": "Textbox",
                                "severity": "P1",
                            }
                        ],
                        "confidence": 0.2,
                    }
                },
                errors=["Element 'Textbox' is invalid"],
            ),
            PhaseAgentResult(
                status="success",
                confidence=0.92,
                output={"runtime_validation": {"status": "success", "errors": [], "confidence": 0.92}},
            ),
        ],
    )

    planner = PlannerAgent(
        agents=[parsing, semantic, spec, transform, export, runtime],
        max_retries=1,
        enable_phase_cache=False,
    )

    ctx = PipelineContext(
        execution_id="rt_route",
        runtime_context={"intent": {"type": "conversion"}},
        artifacts={"source_path": "demo.twbx", "output_path": str(rdl_path)},
    )
    result = planner.run(ctx)

    assert result.status == "success"
    assert runtime.calls == 2
    assert export.calls >= 2
    assert result.phase_results["runtime_validation"].status == "success"
