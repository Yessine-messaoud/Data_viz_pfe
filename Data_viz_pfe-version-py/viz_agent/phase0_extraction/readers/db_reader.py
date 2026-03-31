from __future__ import annotations

from typing import Any


def extract_all_tables(engine: Any) -> list[dict]:
    """Read all base tables from INFORMATION_SCHEMA.TABLES."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")


def extract_columns(engine: Any, schema: str, table: str) -> list[dict]:
    """Read columns from INFORMATION_SCHEMA.COLUMNS."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")


def extract_foreign_keys(engine: Any) -> list[dict]:
    """Read FK metadata from INFORMATION_SCHEMA views."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")


def safe_connect(connection_url: str):
    """Return (engine, None) on success, or (None, error_message) on failure."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")
