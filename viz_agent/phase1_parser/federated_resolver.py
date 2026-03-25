from __future__ import annotations

import re

from lxml import etree

from viz_agent.models.abstract_spec import ResolvedColumn


class FederatedDatasourceResolver:
    AGG_MAP = {
        "sum": "SUM",
        "mn": "MIN",
        "mx": "MAX",
        "avg": "AVG",
        "tmn": "MIN",
        "none": "NONE",
        "pcto": "PERCENT_OF_TOTAL",
        "cnt": "COUNT",
        "cntd": "DISTINCTCOUNT",
        "median": "MEDIAN",
    }

    ROLE_MAP = {
        "qk": "measure",
        "nk": "dimension",
        "ok": "dimension",
        "pk": "dimension",
    }

    def build_table_map(self, twb_xml: etree._Element) -> dict[str, str]:
        table_map: dict[str, str] = {}
        for named_connection in twb_xml.findall('.//named-connection'):
            name = named_connection.get("name", "")
            caption = named_connection.get("caption", name)
            clean = re.sub(r"[^a-zA-Z0-9_]", "_", caption).lower()
            table_map[name] = clean
        return table_map

    def decode_column(self, raw: str, table_map: dict[str, str]) -> ResolvedColumn:
        if raw.startswith("(") or " + " in raw or " - " in raw:
            return ResolvedColumn(
                type="expression",
                raw=raw,
                needs_llm=True,
                table="__expression__",
                column=raw,
            )

        if "Measure Names" in raw or raw == ":Measure Names":
            return ResolvedColumn(
                type="measure_names_placeholder",
                table="__placeholder__",
                column="Measure Names",
            )

        match = re.match(r"federated\.[^.]+\.(\w+):(.+):(\w+)$", raw)
        if match:
            agg, field, role = match.group(1), match.group(2), match.group(3)
            table = self.infer_table(field, table_map)
            return ResolvedColumn(
                type="resolved",
                agg=self.AGG_MAP.get(agg, agg.upper()),
                role=self.ROLE_MAP.get(role, "unknown"),
                table=table,
                column=field,
            )

        return ResolvedColumn(type="simple", table="sales_data", column=raw)

    def infer_table(self, field: str, table_map: dict[str, str]) -> str:
        if field in table_map:
            return table_map[field]

        normalized_field = re.sub(r"[^a-zA-Z0-9]", "", field).lower()
        for original_name, normalized_table in table_map.items():
            normalized_name = re.sub(r"[^a-zA-Z0-9]", "", original_name).lower()
            if normalized_field and (normalized_field in normalized_name or normalized_name in normalized_field):
                return normalized_table

        return next(iter(table_map.values()), "unknown")
