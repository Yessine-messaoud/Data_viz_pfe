from __future__ import annotations

import re

from viz_agent.models.abstract_spec import JoinDef, Measure, TableRef

FK_SUFFIXES = ["Key", "_Key", "KeyID", "_id", "ID", "LineKey"]
MEASURE_KEYWORDS = [
    "Amount",
    "Qty",
    "Quantity",
    "Price",
    "Cost",
    "Revenue",
    "Profit",
    "Sales",
    "Count",
]

FK_PATTERNS = [
    r".*Key$",
    r".*_[Kk]ey$",
    r".*KeyID$",
    r".*LineKey$",
    r"Sum.*Key$",
    r"Sum.*KeyID$",
]


def detect_fact_table(tables: list[TableRef], joins: list[JoinDef]) -> str:
    if not tables:
        return "sales_data"

    scores: dict[str, int] = {table.name: 0 for table in tables}

    for table in tables:
        fk_score = sum(
            3
            for col in table.columns
            if any(col.name.endswith(suffix) for suffix in FK_SUFFIXES)
        )
        measure_score = sum(
            1
            for col in table.columns
            if any(keyword.lower() in col.name.lower() for keyword in MEASURE_KEYWORDS)
        )
        join_score = sum(2 for join in joins if join.left_table == table.name)
        scores[table.name] = fk_score + measure_score + join_score

    exclude = {"date_data", "excel_direct_data"}
    filtered_scores = {name: score for name, score in scores.items() if name not in exclude}
    if not filtered_scores:
        return "sales_data"

    return max(filtered_scores, key=filtered_scores.get)


def filter_fk_measures(measures: list[Measure]) -> list[Measure]:
    def is_fk(measure: Measure) -> bool:
        return any(re.match(pattern, measure.name) for pattern in FK_PATTERNS)

    return [measure for measure in measures if not is_fk(measure)]
