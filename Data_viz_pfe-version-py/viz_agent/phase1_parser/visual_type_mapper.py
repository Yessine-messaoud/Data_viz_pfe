from __future__ import annotations

MARK_TYPE_TO_RDL = {
    "Bar": "chart",
    "Line": "chart",
    "Circle": "chart",
    "Map": "map",
    "Text": "tablix",
    "Square": "tablix",
    "Gantt": "tablix",
    "Pie": "chart",
}


def infer_rdl_visual_type(worksheet_name: str, mark_type: str = "") -> str:
    lowered = worksheet_name.lower()
    if "kpi" in lowered:
        return "textbox"

    if mark_type and mark_type in MARK_TYPE_TO_RDL:
        return MARK_TYPE_TO_RDL[mark_type]

    if any(keyword in lowered for keyword in ("map", "country", "geo", "region")):
        return "map"
    if any(keyword in lowered for keyword in ("trend", "evolution", "time", "month", "year")):
        return "chart"

    return "tablix"
