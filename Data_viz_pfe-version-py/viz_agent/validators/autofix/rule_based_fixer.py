from __future__ import annotations

from copy import deepcopy
from typing import Any


class RuleBasedAutoFixer:
    @staticmethod
    def _infer_business_type(visual: dict[str, Any]) -> str:
        title = str(visual.get("title", "")).lower()
        vid = str(visual.get("id", "")).lower()
        token = f"{title} {vid}"
        if "tree" in token or "treemap" in token:
            return "treemap"
        if "line" in token or "trend" in token:
            return "line"
        if "pie" in token:
            return "pie"
        if "scatter" in token:
            return "scatter"
        if "kpi" in token or str(visual.get("rdl_type", "")).lower() == "textbox":
            return "kpi"
        if str(visual.get("rdl_type", "")).lower() == "map":
            return "map"
        return "bar"

    def apply(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        fixed = deepcopy(payload)
        fixes: list[str] = []

        if "dashboard_spec" in fixed:
            pages = ((fixed.get("dashboard_spec") or {}).get("pages") or [])
            seen_page_names: dict[str, int] = {}
            for page in pages:
                if not isinstance(page, dict):
                    continue
                name = str(page.get("name", "")).strip()
                if not name:
                    page["name"] = f"Page_{len(seen_page_names) + 1}"
                    fixes.append("rule: set missing page name")
                    name = page["name"]

                idx = seen_page_names.get(name, 0)
                seen_page_names[name] = idx + 1
                if idx > 0:
                    page["name"] = f"{name}_{idx+1}"
                    fixes.append("rule: dedupe page name")

                visuals = page.get("visuals", []) or []
                for visual in visuals:
                    if not isinstance(visual, dict):
                        continue
                    if not str(visual.get("title", "")).strip():
                        visual["title"] = str(visual.get("id", "") or "Visual")
                        fixes.append("rule: set missing visual title")
                    vtype = str(visual.get("type", "")).strip().lower()
                    if vtype in {"", "chart"}:
                        inferred = self._infer_business_type(visual)
                        visual["type"] = inferred
                        fixes.append(f"rule: infer business visual type -> {inferred}")
                    if not str(visual.get("rdl_type", "")).strip():
                        visual["rdl_type"] = "chart" if visual.get("type") in {"bar", "line", "pie", "treemap", "scatter"} else "tablix"
                        fixes.append("rule: set missing rdl_type")

        semantic = fixed.get("semantic_model")
        if isinstance(semantic, dict):
            measures = semantic.get("measures")
            if measures is None:
                semantic["measures"] = []
                fixes.append("rule: ensure semantic_model.measures list")

        return fixed, fixes
