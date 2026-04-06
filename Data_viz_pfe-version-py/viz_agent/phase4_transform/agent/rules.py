from __future__ import annotations

from typing import Any


DEFAULT_DATA_TYPE_MAPPINGS: dict[str, dict[str, str]] = {
    "POWERBI": {
        "STRING": "string",
        "TEXT": "string",
        "INTEGER": "int",
        "INT": "int",
        "DECIMAL": "decimal",
        "FLOAT": "decimal",
        "DOUBLE": "decimal",
        "DATE": "date",
        "DATETIME": "datetime",
        "BOOLEAN": "bool",
        "BOOL": "bool",
        "PERCENTAGE": "decimal",
        "CURRENCY": "decimal",
    },
    "TABLEAU": {
        "STRING": "string",
        "TEXT": "string",
        "INTEGER": "integer",
        "INT": "integer",
        "DECIMAL": "float",
        "FLOAT": "float",
        "DOUBLE": "float",
        "DATE": "date",
        "DATETIME": "datetime",
        "BOOLEAN": "boolean",
        "BOOL": "boolean",
        "PERCENTAGE": "float",
        "CURRENCY": "float",
    },
    "RDL": {
        "STRING": "String",
        "TEXT": "String",
        "INTEGER": "Integer",
        "INT": "Integer",
        "DECIMAL": "Decimal",
        "FLOAT": "Decimal",
        "DOUBLE": "Decimal",
        "DATE": "DateTime",
        "DATETIME": "DateTime",
        "BOOLEAN": "Boolean",
        "BOOL": "Boolean",
        "PERCENTAGE": "Decimal",
        "CURRENCY": "Decimal",
    },
}


DEFAULT_VISUAL_MAPPINGS: dict[str, dict[str, str]] = {
    "POWERBI": {
        "bar": "stackedBarChart",
        "line": "lineChart",
        "pie": "pieChart",
        "treemap": "treemap",
        "scatter": "scatterChart",
        "table": "table",
        "kpi": "card",
        "map": "map",
        "gantt": "table",
    },
    "TABLEAU": {
        "bar": "bar",
        "line": "line",
        "pie": "pie",
        "treemap": "square",
        "scatter": "circle",
        "table": "text",
        "kpi": "text",
        "map": "map",
        "gantt": "gantt",
    },
    "RDL": {
        "bar": "ColumnChart",
        "line": "LineChart",
        "pie": "PieChart",
        "treemap": "TreeMap",
        "scatter": "ScatterChart",
        "table": "Tablix",
        "kpi": "Textbox",
        "map": "Map",
        "gantt": "Tablix",
    },
}


UNSUPPORTED_VISUALS: dict[str, set[str]] = {
    "LOOKER": {"treemap", "gantt"},
    "RDL": set(),
    "POWERBI": set(),
    "TABLEAU": set(),
}


def merge_rules(custom_rules: dict[str, Any] | None) -> dict[str, Any]:
    rules = {
        "data_type_mappings": DEFAULT_DATA_TYPE_MAPPINGS,
        "visual_mappings": DEFAULT_VISUAL_MAPPINGS,
        "unsupported_visuals": UNSUPPORTED_VISUALS,
    }
    if not isinstance(custom_rules, dict):
        return rules
    for key in ("data_type_mappings", "visual_mappings", "unsupported_visuals"):
        if key in custom_rules and isinstance(custom_rules[key], dict):
            merged = dict(rules[key])
            merged.update(custom_rules[key])
            rules[key] = merged
    return rules

