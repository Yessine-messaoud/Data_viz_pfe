from __future__ import annotations

import os

import pytest

from viz_agent.models.abstract_spec import CalcField, ParsedWorkbook
from viz_agent.phase2_semantic.semantic_enricher import SemanticEnricher


@pytest.mark.integration
def test_semantic_enricher_requires_mistral_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    workbook = ParsedWorkbook(calculated_fields=[CalcField(name="Profit", expression="SUM([Profit])")])

    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY is required"):
        SemanticEnricher().enrich(workbook, schema_map=None)


@pytest.mark.integration
def test_semantic_enricher_calls_mistral_with_api_key() -> None:
    if not os.getenv("MISTRAL_API_KEY", "").strip():
        pytest.skip("Set MISTRAL_API_KEY to run live Mistral integration test")

    workbook = ParsedWorkbook(
        calculated_fields=[
            CalcField(name="Profit", expression="SUM([Profit])"),
            CalcField(name="Total Sales", expression="SUM([Sales Amount])"),
        ]
    )

    result = SemanticEnricher().enrich(workbook, schema_map=None)

    assert isinstance(result.column_labels, dict)
    assert isinstance(result.hierarchies, list)
    assert isinstance(result.suggested_measures, list)
