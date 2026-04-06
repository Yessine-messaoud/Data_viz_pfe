"""
DataModelTransformer: Converts abstract data model to tool-specific format
"""
from typing import Any, Dict

from .rules import merge_rules

class DataModelTransformer:
    def __init__(self, rules_config=None):
        self.rules = merge_rules(rules_config)

    def _map_data_type(self, source_type: str, target_tool: str) -> str:
        tool = target_tool.upper()
        mappings = self.rules.get("data_type_mappings", {}).get(tool, {})
        key = str(source_type or "STRING").upper()
        return str(mappings.get(key, mappings.get("STRING", "string")))

    def _build_datasets(self, abstract_spec: Dict, target_tool: str) -> list[dict]:
        semantic = abstract_spec.get("semantic_model", {}) if isinstance(abstract_spec, dict) else {}
        entities = semantic.get("entities", []) if isinstance(semantic, dict) else []
        datasets: list[dict] = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            table_name = str(entity.get("name", "")).strip()
            if not table_name:
                continue
            columns = entity.get("columns", []) or []
            fields = []
            for column in columns:
                if not isinstance(column, dict):
                    continue
                name = str(column.get("name", "")).strip()
                if not name:
                    continue
                pbi_type = str(column.get("pbi_type", "STRING"))
                role = str(column.get("role", "unknown"))
                fields.append(
                    {
                        "name": name,
                        "source_type": pbi_type,
                        "target_type": self._map_data_type(pbi_type, target_tool),
                        "role": role,
                    }
                )
            datasets.append({"name": table_name, "fields": fields})
        return datasets

    def _build_visuals(self, abstract_spec: Dict) -> list[dict]:
        visuals: list[dict] = []
        dashboard = abstract_spec.get("dashboard_spec", {}) if isinstance(abstract_spec, dict) else {}
        pages = dashboard.get("pages", []) if isinstance(dashboard, dict) else []
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_name = str(page.get("name", ""))
            for visual in page.get("visuals", []) or []:
                if not isinstance(visual, dict):
                    continue
                binding = visual.get("data_binding", {}) or {}
                axes = binding.get("axes", {}) or {}
                encoding = {}
                if isinstance(axes, dict):
                    for axis_name, axis_payload in axes.items():
                        if isinstance(axis_payload, dict):
                            encoding[axis_name] = axis_payload.get("column") or axis_payload.get("name") or ""
                visuals.append(
                    {
                        "id": visual.get("id"),
                        "title": visual.get("title", ""),
                        "page": page_name,
                        "business_type": str(visual.get("type", "table")).lower(),
                        "rdl_type": str(visual.get("rdl_type", "tablix")).lower(),
                        "encoding": encoding,
                        "position": visual.get("position", {}) or {},
                    }
                )
        return visuals

    def transform(self, abstract_spec: Dict, target_tool: str, context: Dict) -> Dict:
        if not isinstance(abstract_spec, dict):
            return {"error": "abstract_spec must be a dictionary"}

        datasets = self._build_datasets(abstract_spec, target_tool)
        visuals = self._build_visuals(abstract_spec)
        semantic = abstract_spec.get("semantic_model", {}) if isinstance(abstract_spec, dict) else {}
        measures = semantic.get("measures", []) if isinstance(semantic, dict) else []

        return {
            "target_tool": target_tool.upper(),
            "datasets": datasets,
            "visuals": visuals,
            "measures": measures if isinstance(measures, list) else [],
            "parameters": (abstract_spec.get("parameters") or []),
            "filters": ((abstract_spec.get("dashboard_spec") or {}).get("global_filters") or []),
            "meta": {
                "source_spec_id": abstract_spec.get("id", ""),
                "source_spec_version": abstract_spec.get("version", ""),
            },
        }
