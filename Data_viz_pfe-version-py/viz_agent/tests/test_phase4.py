from __future__ import annotations

import os

import pandas as pd
import pytest

from viz_agent.models.abstract_spec import ColumnDef, DataLineageSpec, Measure, SemanticModel, TableRef
from viz_agent.phase0_data.data_source_registry import DataSourceRegistry, ResolvedDataSource
from viz_agent.phase4_transform.calc_field_translator import CalcFieldTranslator
from viz_agent.phase4_transform.rdl_dataset_mapper import RDLDatasetMapper
from viz_agent.validators.expression_validator import ExpressionValidator


class FakeMistralTranslatorClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        idx = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[idx]


def test_rdl_dataset_mapper_builds_dataset_per_table() -> None:
    registry = DataSourceRegistry()
    registry.register(
        "sales_source",
        ResolvedDataSource(
            name="sales_source",
            source_type="db",
            frames={"sales_data": pd.DataFrame({"Sales Amount": [100.0]})},
        ),
    )

    lineage = DataLineageSpec(
        tables=[
            TableRef(
                id="t1",
                name="sales_data",
                columns=[
                    ColumnDef(name="Sales Amount", pbi_type="double"),
                    ColumnDef(name="Customer", pbi_type="text"),
                ],
            )
        ]
    )

    datasets = RDLDatasetMapper.build(registry, lineage)

    assert len(datasets) == 1
    assert datasets[0].name == "sales_data"
    assert datasets[0].fields[0].rdl_type == "Float"
    assert datasets[0].query.upper().startswith("SELECT")


def test_rdl_dataset_mapper_extract_query_sets_sum_decimal_and_count_integer() -> None:
    registry = DataSourceRegistry()
    registry.register(
        "extract_source",
        ResolvedDataSource(
            name="extract_source",
            source_type="hyper",
            frames={"('Extract', 'Extract')": pd.DataFrame({"Country": ["FR"], "TotalSales": [100], "OrderCount": [1]})},
        ),
    )

    lineage = DataLineageSpec(
        tables=[
            TableRef(
                id="t_extract",
                name="('Extract', 'Extract')",
                columns=[
                    ColumnDef(name="Country", pbi_type="text"),
                    ColumnDef(name="TotalSales", pbi_type="text"),
                    ColumnDef(name="TotalTax", pbi_type="text"),
                    ColumnDef(name="TotalFreight", pbi_type="text"),
                    ColumnDef(name="TotalQuantity", pbi_type="text"),
                    ColumnDef(name="OrderCount", pbi_type="text"),
                ],
            )
        ]
    )

    datasets = RDLDatasetMapper.build(registry, lineage)

    fields_by_name = {field.name: field.rdl_type for field in datasets[0].fields}
    assert fields_by_name["TotalSales"] == "Decimal"
    assert fields_by_name["TotalTax"] == "Decimal"
    assert fields_by_name["TotalFreight"] == "Decimal"
    assert fields_by_name["TotalQuantity"] == "Decimal"
    assert fields_by_name["OrderCount"] == "Integer"


def test_calc_field_translator_retries_until_valid_expression() -> None:
    model = SemanticModel(entities=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesAmount")])])
    fake_llm = FakeMistralTranslatorClient(["Not valid", "=Sum(Fields!SalesAmount.Value)"])

    translator = CalcFieldTranslator(llm_client=fake_llm, validator=ExpressionValidator())
    translated = translator.translate("SUM([Sales Amount])", model)

    assert translated == "=Sum(Fields!SalesAmount.Value)"
    assert fake_llm.calls >= 2


def test_calc_field_translator_uses_adventureworks_override() -> None:
    model = SemanticModel(entities=[])
    fake_llm = FakeMistralTranslatorClient(["=0"])
    translator = CalcFieldTranslator(llm_client=fake_llm, validator=ExpressionValidator())

    translated = translator.translate("Calculation_1259319095595331584", model)

    assert translated == "=Sum(Fields!Profit.Value)"
    assert fake_llm.calls == 0


@pytest.mark.integration
def test_calc_field_translator_calls_mistral_live() -> None:
    if not os.getenv("MISTRAL_API_KEY", "").strip():
        pytest.skip("Set MISTRAL_API_KEY to run live Mistral translation test")

    model = SemanticModel(entities=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesAmount")])])
    translator = CalcFieldTranslator(validator=ExpressionValidator())

    translated = translator.translate("SUM([Sales Amount])", model)
    assert isinstance(translated, str)
    assert len(translated) > 0
