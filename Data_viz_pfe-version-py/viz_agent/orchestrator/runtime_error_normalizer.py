from __future__ import annotations

from typing import Any


def normalize_runtime_error(raw_error: str, *, location: str = "", severity: str | None = None) -> dict[str, str]:
    message = str(raw_error or "Unknown runtime validation error").strip()
    lowered = message.lower()

    error_type = "rendering_error"
    detected_location = location or "unknown"
    level = (severity or "P2").upper()

    if "datasource" in lowered or "connectstring" in lowered or "dataset" in lowered:
        error_type = "datasource_error"
        level = "P1"
    elif "xml" in lowered or "schema" in lowered or "namespace" in lowered or "element" in lowered:
        error_type = "schema_error"
        level = "P1"

    if "textbox" in lowered:
        detected_location = "Textbox"
    elif "tablix" in lowered:
        detected_location = "Tablix"
    elif "chart" in lowered:
        detected_location = "Chart"
    elif "datasource" in lowered:
        detected_location = "DataSource"

    return {
        "type": error_type,
        "message": message,
        "location": detected_location,
        "severity": level,
    }


def normalize_issue_object(issue: Any) -> dict[str, str]:
    code = str(getattr(issue, "code", "") or "")
    message = str(getattr(issue, "message", "") or "")
    location = str(getattr(issue, "location", "") or "")
    severity = str(getattr(issue, "severity", "") or "")
    merged = f"{code}: {message}" if code else message
    return normalize_runtime_error(merged, location=location, severity=_to_p_level(severity))


def _to_p_level(severity: str) -> str:
    low = str(severity or "").lower()
    if low == "error":
        return "P1"
    if low == "warning":
        return "P2"
    return "P3"
