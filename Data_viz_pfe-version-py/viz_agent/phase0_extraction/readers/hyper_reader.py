from __future__ import annotations


def list_all_tables(hyper_path: str) -> list[dict]:
    """List all tables in all schemas from a Hyper file."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")


def get_table_schema(hyper_path: str, schema: str, table: str) -> list[dict]:
    """Return column metadata for a Hyper table."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")


def get_row_count(hyper_path: str, schema: str, table: str) -> int:
    """Return table row count when explicitly requested."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 2")
