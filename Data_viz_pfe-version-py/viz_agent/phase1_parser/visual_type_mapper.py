from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VISUAL_MAPPING: dict[str, dict[str, str]] = {
    "bar": {"logical": "bar", "rdl": "ColumnChart", "series": "Column"},
    "line": {"logical": "line", "rdl": "LineChart", "series": "Line"},
    "pie": {"logical": "pie", "rdl": "PieChart", "series": "Pie"},
    "treemap": {"logical": "treemap", "rdl": "TreeMap", "series": "Column"},
    "scatter": {"logical": "scatter", "rdl": "ScatterChart", "series": "Scatter"},
    "map": {"logical": "map", "rdl": "Map"},
    "table": {"logical": "table", "rdl": "Tablix"},
    "kpi": {"logical": "kpi", "rdl": "Textbox"},
    "gantt": {"logical": "gantt", "rdl": "Tablix"},
}


@dataclass(frozen=True)
class VisualTypeResolution:
    logical_type: str
    rdl_type: str
    confidence: float
    warning: str = ""
    series_type: str | None = None


def _normalize_mark_type(mark_type: str) -> str:
    return str(mark_type or "").strip().lower()


def _encoding_fields(encoding: Any | None) -> list[str]:
    if encoding is None:
        return []
    if hasattr(encoding, "model_dump"):
        encoding = encoding.model_dump()
    if not isinstance(encoding, dict):
        return []
    return [str(encoding.get(field, "") or "").strip() for field in ("x", "y", "color", "size", "detail") if encoding.get(field)]


def _resolve_generic_chart_from_encoding(encoding_payload: dict[str, Any], worksheet_name: str) -> tuple[str, float, str]:
    lowered_name = str(worksheet_name or "").lower()
    has_x = bool(encoding_payload.get("x"))
    has_y = bool(encoding_payload.get("y"))
    has_color = bool(encoding_payload.get("color"))
    has_size = bool(encoding_payload.get("size"))
    has_detail = bool(encoding_payload.get("detail"))

    if has_size and has_color and not has_x and not has_y:
        return "treemap", 0.82, "generic chart resolved to treemap from size+color encoding"
    if has_x and has_y:
        return "bar", 0.74, "generic chart resolved to bar from x+y encoding"
    if has_y and not has_x:
        return "kpi", 0.78, "generic chart resolved to kpi from single measure encoding"
    if any(keyword in lowered_name for keyword in ("map", "country", "geo", "region")):
        return "map", 0.7, "generic chart resolved to map from worksheet naming"
    if has_detail and has_y:
        return "line", 0.68, "generic chart resolved to line from detail+y encoding"
    return "table", 0.55, "generic chart fallback to table due to insufficient encoding"


def resolve_visual_mapping(
    worksheet_name: str,
    mark_type: str = "",
    encoding: Any | None = None,
) -> VisualTypeResolution:
    lowered_name = str(worksheet_name or "").lower()
    normalized_mark = _normalize_mark_type(mark_type)
    encoding_fields = _encoding_fields(encoding)
    encoding_payload = encoding.model_dump() if hasattr(encoding, "model_dump") else encoding if isinstance(encoding, dict) else {}

    if normalized_mark == "chart":
        logical_type, confidence, warning = _resolve_generic_chart_from_encoding(encoding_payload, worksheet_name)
    elif normalized_mark == "automatic":
        has_x = bool(encoding_payload.get("x"))
        has_y = bool(encoding_payload.get("y"))
        measure_like_fields = [field for field in (encoding_payload.get("x"), encoding_payload.get("y"), encoding_payload.get("color"), encoding_payload.get("size"), encoding_payload.get("detail")) if field]

        if encoding_payload.get("size") and encoding_payload.get("color") and not has_x and not has_y:
            logical_type = "treemap"
            confidence = 0.82
        elif "kpi" in lowered_name or (len(measure_like_fields) == 1 and not has_x and not has_y):
            logical_type = "kpi"
            confidence = 0.8
        elif has_x and has_y:
            logical_type = "bar"
            confidence = 0.74
        elif len(measure_like_fields) >= 2:
            logical_type = "line"
            confidence = 0.78
        elif any(keyword in lowered_name for keyword in ("map", "country", "geo", "region")):
            logical_type = "map"
            confidence = 0.7
        else:
            logical_type = "table"
            confidence = 0.55
        warning = "automatic mark type resolved from encoding"
    else:
        mark_aliases = {
            "bar": "bar",
            "line": "line",
            "circle": "scatter",
            "scatter": "scatter",
            "map": "map",
            "text": "table",
            "square": "treemap",
            "treemap": "treemap",
            "gantt": "gantt",
            "pie": "pie",
            "automatic": "table",
        }
        if "kpi" in lowered_name:
            logical_type = "kpi"
            confidence = 0.72
            warning = "worksheet name suggests KPI"
        elif normalized_mark in mark_aliases:
            logical_type = mark_aliases[normalized_mark]
            confidence = 0.95 if normalized_mark else 0.5
            warning = ""
        elif "treemap" in lowered_name:
            logical_type = "treemap"
            confidence = 0.7
            warning = "worksheet name suggests treemap"
        elif any(keyword in lowered_name for keyword in ("map", "country", "geo", "region")):
            logical_type = "map"
            confidence = 0.68
            warning = "worksheet name suggests map"
        elif any(keyword in lowered_name for keyword in ("trend", "evolution", "time", "month", "year")):
            logical_type = "line"
            confidence = 0.68
            warning = "worksheet name suggests line"
        else:
            logical_type = "table"
            confidence = 0.5
            warning = f"unknown mark type '{mark_type}' resolved to table"

    mapping = VISUAL_MAPPING.get(logical_type, VISUAL_MAPPING["table"])
    series_type = mapping.get("series")
    return VisualTypeResolution(
        logical_type=mapping["logical"],
        rdl_type=mapping["rdl"],
        confidence=confidence,
        warning=warning,
        series_type=series_type,
    )


def infer_logical_visual_type(worksheet_name: str, mark_type: str = "", encoding: Any | None = None) -> str:
    return resolve_visual_mapping(worksheet_name, mark_type, encoding).logical_type


def infer_rdl_visual_type(worksheet_name: str, mark_type: str = "", encoding: Any | None = None) -> str:
    return resolve_visual_mapping(worksheet_name, mark_type, encoding).rdl_type


def infer_chart_series_type(worksheet_name: str, mark_type: str = "", encoding: Any | None = None) -> str:
    """Return the SSRS ChartSeries Type value for chart visuals."""
    resolution = resolve_visual_mapping(worksheet_name, mark_type, encoding)
    if resolution.series_type:
        return resolution.series_type
    return "Column"
