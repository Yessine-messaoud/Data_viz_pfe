from __future__ import annotations

import json

from viz_agent.models.abstract_spec import DataLineageSpec


class LineageQueryService:
    def __init__(self, lineage: DataLineageSpec):
        self.lineage = lineage

    def to_dict(self) -> dict:
        return self.lineage.model_dump()

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=True)

    def list_tables(self) -> list[str]:
        return [table.name for table in self.lineage.tables]

    def list_joins(self) -> list[dict]:
        return [join.model_dump() for join in self.lineage.joins]

    def build_select_all(self, table_name: str) -> str:
        return f"SELECT * FROM {table_name}"
