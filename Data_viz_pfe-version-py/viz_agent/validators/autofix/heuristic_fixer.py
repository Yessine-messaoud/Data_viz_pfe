from __future__ import annotations

from copy import deepcopy
from difflib import get_close_matches
from typing import Any


class HeuristicAutoFixer:
    def apply(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        fixed = deepcopy(payload)
        fixes: list[str] = []

        semantic_cols = self._semantic_columns(fixed.get("semantic_model") or {})
        if not semantic_cols:
            return fixed, fixes

        pages = ((fixed.get("dashboard_spec") or {}).get("pages") or [])
        for page in pages:
            if not isinstance(page, dict):
                continue
            for visual in page.get("visuals", []) or []:
                if not isinstance(visual, dict):
                    continue
                axes = ((visual.get("data_binding") or {}).get("axes") or {})
                for axis_name, axis_value in axes.items():
                    if not isinstance(axis_value, dict):
                        continue
                    col = str(axis_value.get("column", "")).strip()
                    if not col or col in semantic_cols:
                        continue
                    candidate = get_close_matches(col, semantic_cols, n=1, cutoff=0.85)
                    if candidate:
                        axis_value["column"] = candidate[0]
                        fixes.append(f"heuristic: remap axis '{col}' -> '{candidate[0]}' ({axis_name})")

        return fixed, fixes

    def _semantic_columns(self, semantic: dict[str, Any]) -> list[str]:
        cols: list[str] = []
        for entity in semantic.get("entities", []) or []:
            if not isinstance(entity, dict):
                continue
            for col in entity.get("columns", []) or []:
                if not isinstance(col, dict):
                    continue
                name = str(col.get("name", "")).strip()
                if name:
                    cols.append(name)
        return cols

