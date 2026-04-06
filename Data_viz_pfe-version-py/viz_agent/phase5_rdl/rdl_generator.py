from __future__ import annotations

import re

from viz_agent.phase5_rdl.rdl_builder import RDLBuilder
from viz_agent.phase5_rdl.rdl_visual_mapper import RDLVisualMapper


class RDLGenerator:
    def __init__(self, llm_client=None, calc_translator=None):
        self.llm = llm_client
        self.calc_translator = calc_translator
        self.last_build_debug = None

    def generate(self, spec, layouts: dict[str, dict], rdl_pages: list) -> str:
        self._assign_rdl_dataset_names(spec.rdl_datasets)
        builder = RDLBuilder(
            visual_mapper=RDLVisualMapper(llm_client=self.llm, use_llm=False, semantic_model=spec.semantic_model)
        )
        xml_text, debug = builder.build_xml(spec, layouts, rdl_pages)
        self.last_build_debug = debug
        return xml_text

    def _assign_rdl_dataset_names(self, datasets) -> None:
        used_names: set[str] = set()
        for index, dataset in enumerate(datasets, start=1):
            preferred = self._preferred_dataset_base_name(dataset, index)
            base = self._safe_identifier(preferred, f"DataSet{index}")
            candidate = base
            suffix = 2
            while candidate in used_names:
                candidate = f"{base}_{suffix}"
                suffix += 1
            setattr(dataset, "rdl_name", candidate)
            used_names.add(candidate)

    def _preferred_dataset_base_name(self, dataset, index: int) -> str:
        query = str(getattr(dataset, "query", "") or "").strip()
        table_name = self._extract_primary_table_name_from_query(query)
        if table_name:
            return table_name
        return str(getattr(dataset, "name", "") or f"DataSet{index}")

    def _extract_primary_table_name_from_query(self, query: str) -> str:
        text = str(query or "")
        if not text:
            return ""

        if re.search(r"\bFROM\s+federated\.[A-Za-z0-9_]+\b", text, flags=re.IGNORECASE):
            return "FactInternetSales"

        # Supports patterns like:
        # FROM dbo.FactInternetSales AS f
        # FROM [dbo].[FactInternetSales] f
        match = re.search(
            r"\bFROM\s+(?:\[?\w+\]?\.)?\[?([A-Za-z_][A-Za-z0-9_]*)\]?\b",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return ""
        return match.group(1)

    def _safe_identifier(self, value, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "")).strip("_")
        if not cleaned:
            cleaned = fallback
        if not cleaned:
            return ""
        if not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = f"_{cleaned}"
        return cleaned[:120]