from __future__ import annotations

import re

FIELDS_PATTERN = re.compile(r"=Fields!([A-Za-z_][A-Za-z0-9_]*)\\.Value")
PARAM_PATTERN = re.compile(r"=Parameters!([A-Za-z_][A-Za-z0-9_]*)\\.Value")


def extract_field_refs(text: str) -> list[str]:
    if not text:
        return []
    return FIELDS_PATTERN.findall(text)


def extract_param_refs(text: str) -> list[str]:
    if not text:
        return []
    return PARAM_PATTERN.findall(text)
