from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd

@dataclass
class ResolvedDataSource:
    name: str
    source_type: str
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    connection_config: dict = field(default_factory=dict)

class DataSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, ResolvedDataSource] = {}

    def register(self, name: str, source: ResolvedDataSource) -> None:
        self._sources[name] = source

    def get(self, name: str) -> ResolvedDataSource | None:
        return self._sources.get(name)

    def all_frames(self) -> dict[str, pd.DataFrame]:
        result: dict[str, pd.DataFrame] = {}
        for source in self._sources.values():
            result.update(source.frames)
        return result

    def get_sql_query(self, table_name: str) -> str:
        src = self._get_source_for_table(table_name)
        if src and src.source_type == "db":
            return f"SELECT * FROM {table_name}"
        return f"SELECT * FROM {table_name}"

    def _get_source_for_table(self, table_name: str) -> ResolvedDataSource | None:
        for source in self._sources.values():
            if table_name in source.frames:
                return source
        return None
