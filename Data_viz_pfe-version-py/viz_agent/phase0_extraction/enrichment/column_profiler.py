from __future__ import annotations

from typing import Any


def profile_column(engine: Any, schema: str, table: str, column: str) -> dict:
    """Return sampled profiling metrics: distinct_count and null_ratio."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")
