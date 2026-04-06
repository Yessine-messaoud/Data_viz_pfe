from __future__ import annotations

from typing import Any

from viz_agent.phase0_extraction.models import Relationship, Table


def detect_from_fk(engine: Any) -> list[Relationship]:
    """Detect relationships from database foreign key metadata."""
    if engine is None:
        return []

    try:
        from sqlalchemy import inspect
    except Exception:
        return []

    inspector = inspect(engine)
    relationships: list[Relationship] = []

    try:
        table_names = inspector.get_table_names()
    except Exception:
        return []

    for table_name in table_names:
        try:
            foreign_keys = inspector.get_foreign_keys(table_name) or []
        except Exception:
            continue

        for fk in foreign_keys:
            source_cols = fk.get("constrained_columns") or []
            target_cols = fk.get("referred_columns") or []
            target_table = fk.get("referred_table") or ""
            if not target_table:
                continue

            for idx, source_col in enumerate(source_cols):
                target_col = target_cols[idx] if idx < len(target_cols) else (target_cols[0] if target_cols else "id")
                relationships.append(
                    Relationship(
                        source_table=table_name,
                        source_column=source_col,
                        target_table=target_table,
                        target_column=target_col,
                        type="foreign_key",
                    )
                )

    return _dedupe_relationships(relationships)


def detect_from_heuristics(tables: list[Table]) -> list[Relationship]:
    """Infer relationships with naming heuristics such as *ID and *Key."""
    relationships: list[Relationship] = []
    if not tables:
        return relationships

    table_by_name = {_norm_table_name(table.name): table for table in tables}
    columns_by_table = {table.name: {col.name.lower(): col.name for col in table.columns} for table in tables}

    for source_table in tables:
        source_cols = columns_by_table.get(source_table.name, {})
        for source_col_lc, source_col in source_cols.items():
            if not _is_key_like(source_col_lc):
                continue

            base = _base_name(source_col_lc)
            target = _find_target_table(base, source_table.name, tables, table_by_name)
            if target is not None:
                target_col = _pick_target_column(target, base)
                if target_col:
                    relationships.append(
                        Relationship(
                            source_table=source_table.name,
                            source_column=source_col,
                            target_table=target.name,
                            target_column=target_col,
                            type="inferred_suffix",
                        )
                    )
                    continue

            # Secondary heuristic: same key-like column appears in one unique other table.
            other_tables = []
            for candidate in tables:
                if candidate.name == source_table.name:
                    continue
                candidate_cols = {c.name.lower(): c.name for c in candidate.columns}
                if source_col_lc in candidate_cols:
                    other_tables.append((candidate, candidate_cols[source_col_lc]))
            if len(other_tables) == 1:
                candidate_table, candidate_col = other_tables[0]
                relationships.append(
                    Relationship(
                        source_table=source_table.name,
                        source_column=source_col,
                        target_table=candidate_table.name,
                        target_column=candidate_col,
                        type="inferred_name",
                    )
                )

    return _dedupe_relationships(relationships)


def _norm_table_name(table_name: str) -> str:
    value = table_name.lower()
    if "." in value:
        value = value.split(".")[-1]
    return value


def _singularize(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 1:
        return token[:-1]
    return token


def _is_key_like(col_name: str) -> bool:
    return (
        col_name.endswith("id")
        or col_name.endswith("_id")
        or col_name.endswith("key")
        or col_name.endswith("_key")
    )


def _base_name(col_name: str) -> str:
    token = col_name
    for suffix in ("_id", "id", "_key", "key"):
        if token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    token = token.strip("_")
    return _singularize(token)


def _find_target_table(base: str, source_table_name: str, tables: list[Table], table_by_name: dict[str, Table]) -> Table | None:
    if not base:
        return None

    candidates = [base, base + "s", base + "es"]
    for candidate_name in candidates:
        table = table_by_name.get(candidate_name)
        if table and table.name != source_table_name:
            return table

    # fallback approximate match
    for table in tables:
        normalized = _norm_table_name(table.name)
        if table.name == source_table_name:
            continue
        if normalized.startswith(base) or base.startswith(normalized):
            return table
    return None


def _pick_target_column(target_table: Table, base: str) -> str | None:
    columns = {col.name.lower(): col.name for col in target_table.columns}
    candidates = [
        "id",
        f"{_singularize(_norm_table_name(target_table.name))}_id",
        f"{base}_id",
        f"{base}key",
        f"{base}_key",
    ]
    for candidate in candidates:
        if candidate in columns:
            return columns[candidate]
    return None


def _dedupe_relationships(relationships: list[Relationship]) -> list[Relationship]:
    deduped: list[Relationship] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for rel in relationships:
        key = (rel.source_table, rel.source_column, rel.target_table, rel.target_column, rel.type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rel)
    return deduped
