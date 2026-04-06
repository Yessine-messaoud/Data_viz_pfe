from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChartTypeRule:
    logical_type: str
    rdl_visual_type: str
    series_type: str
    series_subtype: str | None = None


# Single source of truth for chart conversions across parser/spec/rdl.
CHART_TYPE_REGISTRY: dict[str, ChartTypeRule] = {
    "bar": ChartTypeRule(logical_type="bar", rdl_visual_type="chart", series_type="Column"),
    "line": ChartTypeRule(logical_type="line", rdl_visual_type="chart", series_type="Line"),
    "scatter": ChartTypeRule(logical_type="scatter", rdl_visual_type="chart", series_type="Scatter"),
    "pie": ChartTypeRule(logical_type="pie", rdl_visual_type="chart", series_type="Shape", series_subtype="Pie"),
    # Treemap is not natively represented as a dedicated SSRS chart type here;
    # keep a stable fallback until a dedicated renderer is implemented.
    "treemap": ChartTypeRule(logical_type="treemap", rdl_visual_type="chart", series_type="Column"),
}

NON_CHART_VISUAL_TYPES: dict[str, str] = {
    "table": "tablix",
    "gantt": "tablix",
    "kpi": "textbox",
    "map": "map",
}


def is_chart_logical_type(logical_type: str) -> bool:
    return logical_type.strip().lower() in CHART_TYPE_REGISTRY


def rdl_visual_type_for(logical_type: str) -> str:
    key = logical_type.strip().lower()
    if key in CHART_TYPE_REGISTRY:
        return CHART_TYPE_REGISTRY[key].rdl_visual_type
    return NON_CHART_VISUAL_TYPES.get(key, "tablix")


def series_rule_for(logical_type: str) -> ChartTypeRule | None:
    return CHART_TYPE_REGISTRY.get(logical_type.strip().lower())


def series_from_override(override: str) -> tuple[str, str | None] | None:
    normalized = str(override or "").strip().lower()
    if normalized in {"column", "line", "scatter", "bar", "area", "treemap"}:
        return {
            "column": ("Column", None),
            "line": ("Line", None),
            "scatter": ("Scatter", None),
            "bar": ("Bar", None),
            "area": ("Area", None),
            "treemap": ("Column", None),
        }[normalized]
    if normalized == "pie":
        return ("Shape", "Pie")
    return None


def allowed_series_overrides() -> set[str]:
    return {"column", "line", "scatter", "bar", "area", "pie", "treemap"}
