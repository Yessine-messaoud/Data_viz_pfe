from __future__ import annotations

import re

from viz_agent.models.abstract_spec import ColumnRef


def _clean_identifier(value: str) -> str:
    return value.strip().strip("[]").strip()


def decode_column_ref(raw: str, default_table: str = "") -> ColumnRef:
    token = raw.strip()
    if not token:
        return ColumnRef(table=default_table or "unknown", column="unknown")

    # Expected Tableau federated form:
    # [federated.0data1].[sum:TotalSales:qk]
    federated_match = re.match(r"^\[(?P<table>[^\]]+)\]\.\[(?P<field>[^\]]+)\]$", token)
    if federated_match:
        table_name = _clean_identifier(federated_match.group("table"))
        field_token = _clean_identifier(federated_match.group("field"))
        field_parts = field_token.split(":")
        if len(field_parts) >= 2:
            # keep business field name only, not agg/role suffix
            column_name = field_parts[1]
        else:
            column_name = field_token
        return ColumnRef(table=table_name or default_table or "unknown", column=column_name or "unknown")

    simple_token = _clean_identifier(token)
    if "." in simple_token:
        parts = [p for p in simple_token.split(".") if p]
        if len(parts) >= 2:
            return ColumnRef(table=parts[-2], column=parts[-1])

    return ColumnRef(table=default_table or "unknown", column=simple_token or "unknown")
