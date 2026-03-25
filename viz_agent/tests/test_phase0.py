from __future__ import annotations

import pandas as pd

from viz_agent.phase0_data.data_source_registry import DataSourceRegistry, ResolvedDataSource


def test_registry_returns_all_frames() -> None:
    registry = DataSourceRegistry()
    df1 = pd.DataFrame({"a": [1, 2]})
    df2 = pd.DataFrame({"b": [3, 4]})

    registry.register("src1", ResolvedDataSource("src1", "csv", {"table1": df1}))
    registry.register("src2", ResolvedDataSource("src2", "hyper", {"table2": df2}))

    all_frames = registry.all_frames()
    assert "table1" in all_frames
    assert "table2" in all_frames
    assert len(all_frames) == 2


def test_registry_generates_sql_query() -> None:
    registry = DataSourceRegistry()
    df = pd.DataFrame({"col": [1]})
    registry.register("db_src", ResolvedDataSource("db_src", "db", {"orders": df}))

    query = registry.get_sql_query("orders")
    assert "orders" in query.lower()
    assert query.strip().upper().startswith("SELECT")
