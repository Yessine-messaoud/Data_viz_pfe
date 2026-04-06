from __future__ import annotations

from pathlib import Path

from viz_agent.orchestrator.user_intent_detection_agent import UserIntentDetectionAgent


def test_detect_convert_without_modifications_fr() -> None:
    agent = UserIntentDetectionAgent()

    intent = agent.detect(
        "Convertir ce dashboard sans modification en RDL.",
        input_path=Path("demo.twbx"),
        output_path=Path("demo.rdl"),
    )

    assert intent["type"] == "conversion"
    assert intent["action"] == "convert_dashboard_without_changes"
    assert intent["artifacts"]["output_format"] == "rdl"
    assert intent["intent_detection"]["language"] in {"fr", "mixed"}


def test_detect_convert_with_modifications_en() -> None:
    agent = UserIntentDetectionAgent()

    intent = agent.detect(
        "Convert this BI report with modifications: add filter on country and change bar chart to line chart in PDF.",
        input_path=Path("report.twbx"),
        output_path=Path("report.rdl"),
    )

    assert intent["type"] in {"optimization", "conversion"}
    assert intent["action"] == "convert_bi_with_modifications"
    assert intent["constraints"]["requested_output_format"] == "pdf"
    assert intent["constraints"]["requested_modifications"]


def test_detect_create_dashboard_from_scratch_with_chart_specs() -> None:
    agent = UserIntentDetectionAgent()

    intent = agent.detect(
        "Create dashboard from scratch with bar chart, line chart and KPI tiles, export html.",
        input_path=Path("empty.twb"),
        output_path=Path("new_dashboard.html"),
    )

    assert intent["type"] == "generation"
    assert intent["action"] == "create_dashboard_from_scratch"
    assert "bar chart" in intent["intent_detection"]["chart_specs"]
    assert "line chart" in intent["intent_detection"]["chart_specs"]
    assert intent["constraints"]["requested_output_format"] == "html"


def test_detect_respects_intent_override() -> None:
    agent = UserIntentDetectionAgent()

    intent = agent.detect(
        "Convert without changes.",
        input_path=Path("demo.twbx"),
        output_path=Path("demo.rdl"),
        intent_type_override="analysis",
    )

    assert intent["type"] == "analysis"
    assert intent["action"] == "analyze_dashboard_request"
