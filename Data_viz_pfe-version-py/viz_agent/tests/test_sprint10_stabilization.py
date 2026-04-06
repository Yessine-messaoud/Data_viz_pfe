from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from viz_agent.main import run_pipeline
from viz_agent.phase0_extraction.hyper_extractor import HyperExtractor
from viz_agent.phase1_parser.tableau_parser import TableauParser
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry


def test_run_pipeline_fails_when_input_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    with pytest.raises(FileNotFoundError):
        import asyncio

        asyncio.run(run_pipeline("does_not_exist.twbx", "out.rdl"))


def test_parser_fails_on_invalid_xml(tmp_path: Path) -> None:
    bad_twbx = tmp_path / "bad.twbx"
    with zipfile.ZipFile(bad_twbx, "w") as archive:
        archive.writestr("broken.twb", "<workbook><invalid></workbook")

    parser = TableauParser()
    with pytest.raises(ValueError, match="Invalid TWB XML"):
        parser.parse(str(bad_twbx), DataSourceRegistry())


def test_hyper_extractor_raises_if_no_dependency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("viz_agent.phase0_extraction.hyper_extractor.PANTAB_AVAILABLE", False)

    def _raise_native(_self, _hyper_path):
        raise RuntimeError("Hyper extraction requires pantab or tableauhyperapi. Install one of them.")

    monkeypatch.setattr(HyperExtractor, "_extract_native", _raise_native)

    twbx = tmp_path / "sample.twbx"
    with zipfile.ZipFile(twbx, "w") as archive:
        archive.writestr("Data/sample.hyper", "dummy")

    extractor = HyperExtractor()
    with pytest.raises(RuntimeError, match="requires pantab or tableauhyperapi"):
        extractor.extract_from_twbx(str(twbx))


@pytest.mark.integration
def test_pipeline_integration_demo_twbx_live(tmp_path: Path) -> None:
    if not os.getenv("MISTRAL_API_KEY", "").strip():
        pytest.skip("Set MISTRAL_API_KEY to run full pipeline integration")

    twb_content = """<?xml version='1.0' encoding='utf-8'?>
    <workbook>
      <datasources>
        <datasource name='sales_data' caption='Sales'>
          <connection class='textscan'/>
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
      <column name='[Profit]' formula='SUM([Profit])'/>
    </workbook>
    """

    twbx = tmp_path / "demo.twbx"
    with zipfile.ZipFile(twbx, "w") as archive:
        archive.writestr("demo.twb", twb_content)

    output = tmp_path / "output.rdl"

    import asyncio

    asyncio.run(run_pipeline(str(twbx), str(output)))

    assert output.exists()
    assert output.with_name("output_lineage.json").exists()
