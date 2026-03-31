import pandas as pd

from viz_agent.phase2_semantic.profiling import ColumnProfiler


def test_column_profiler_basic_roles():
    df = pd.DataFrame(
        {
            "Amount": [10, 20, None],
            "Country": ["FR", "US", "FR"],
            "OrderDate": pd.to_datetime(["2020-01-01", "2020-01-02", None]),
        }
    )
    profiler = ColumnProfiler()
    profiles = profiler.profile_dataset("sales", df)

    roles = {p.name: p.role for p in profiles}
    assert roles["Amount"] == "measure"
    assert roles["Country"] == "dimension"
    assert roles["OrderDate"] == "date"

    dc = {p.name: p.distinct_count for p in profiles}
    assert dc["Country"] == 2

    nr = {p.name: p.null_ratio for p in profiles}
    assert nr["Amount"] > 0
    assert nr["OrderDate"] > 0
