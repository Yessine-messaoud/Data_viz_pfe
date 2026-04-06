from __future__ import annotations

from viz_agent.models.abstract_spec import DataSource, JoinDef


class JoinResolver:
    def resolve(
        self,
        datasources: list[DataSource],
        tableau_relationships: list[dict] | None = None,
        table_name_map: dict[str, str] | None = None,
    ) -> list[JoinDef]:
        if tableau_relationships:
            source_joins = self._resolve_from_tableau_relationships(tableau_relationships, table_name_map)
            if source_joins:
                return source_joins

        inferred = self._resolve_from_columns(datasources, table_name_map)
        if inferred:
            return inferred

        # Final conservative fallback when no relationship can be inferred.
        joins: list[JoinDef] = []
        for index, datasource in enumerate(datasources):
            if index + 1 >= len(datasources):
                continue
            left = self._resolve_table_name(datasource.name or datasource.caption or f"table_{index}", table_name_map)
            right_ds = datasources[index + 1]
            right = self._resolve_table_name(right_ds.name or right_ds.caption or f"table_{index + 1}", table_name_map)
            joins.append(
                JoinDef(
                    id=f"join_{index}",
                    left_table=left,
                    right_table=right,
                    left_col="id",
                    right_col="id",
                )
            )
        return joins

    def _resolve_from_columns(self, datasources: list[DataSource], table_name_map: dict[str, str] | None) -> list[JoinDef]:
        joins: list[JoinDef] = []
        seen: set[tuple[str, str, str, str]] = set()

        normalized_columns: list[tuple[str, list[str]]] = []
        for index, ds in enumerate(datasources):
            table_name = self._resolve_table_name(ds.name or ds.caption or f"table_{index}", table_name_map)
            cols = [str(getattr(col, "name", "") or "").strip() for col in (ds.columns or [])]
            cols = [c for c in cols if c]
            normalized_columns.append((table_name, cols))

        for i in range(len(normalized_columns)):
            left_table, left_cols = normalized_columns[i]
            left_lc = {c.lower(): c for c in left_cols}
            for j in range(i + 1, len(normalized_columns)):
                right_table, right_cols = normalized_columns[j]
                right_lc = {c.lower(): c for c in right_cols}

                best = self._best_join_candidate(left_lc, right_lc)
                if best is None:
                    continue

                left_col, right_col = best
                key = (left_table.lower(), right_table.lower(), left_col.lower(), right_col.lower())
                if key in seen:
                    continue
                seen.add(key)

                joins.append(
                    JoinDef(
                        id=f"join_inferred_{len(joins)}",
                        left_table=left_table,
                        right_table=right_table,
                        left_col=left_col,
                        right_col=right_col,
                        type="INNER",
                        source_xml_ref="inferred_from_columns",
                    )
                )

        return joins

    def _best_join_candidate(self, left_lc: dict[str, str], right_lc: dict[str, str]) -> tuple[str, str] | None:
        common = sorted(set(left_lc.keys()) & set(right_lc.keys()))
        for col in common:
            if col in {"id"} or col.endswith("id") or col.endswith("_id") or col.endswith("key") or col.endswith("_key"):
                return (left_lc[col], right_lc[col])

        # Typical FK naming: <table>id on one side, id on another.
        for l_low, l_raw in left_lc.items():
            if l_low.endswith("id") and "id" in right_lc:
                return (l_raw, right_lc["id"])
        for r_low, r_raw in right_lc.items():
            if r_low.endswith("id") and "id" in left_lc:
                return (left_lc["id"], r_raw)

        return None

    def _resolve_table_name(self, table_name: str, table_name_map: dict[str, str] | None) -> str:
        raw = str(table_name or "").strip()
        if not raw:
            return "unknown_table"
        if not table_name_map:
            return raw

        candidates = [raw, raw.strip("[]"), raw.lower(), raw.strip("[]").lower()]
        for candidate in candidates:
            mapped = table_name_map.get(candidate)
            if mapped:
                return str(mapped)
        return raw

    def _resolve_from_tableau_relationships(
        self,
        tableau_relationships: list[dict],
        table_name_map: dict[str, str] | None,
    ) -> list[JoinDef]:
        joins: list[JoinDef] = []
        seen: set[tuple[str, str, str, str, str]] = set()

        for index, rel in enumerate(tableau_relationships):
            left_table = self._resolve_table_name(str(rel.get("left_table", "") or ""), table_name_map)
            right_table = self._resolve_table_name(str(rel.get("right_table", "") or ""), table_name_map)
            left_col = str(rel.get("left_col", "") or "id").strip() or "id"
            right_col = str(rel.get("right_col", "") or "id").strip() or "id"

            join_type = str(rel.get("type", "INNER") or "INNER").strip().upper()
            if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
                join_type = "INNER"

            if not left_table or not right_table:
                continue

            dedup_key = (
                left_table.lower(),
                right_table.lower(),
                left_col.lower(),
                right_col.lower(),
                join_type,
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            joins.append(
                JoinDef(
                    id=f"join_src_{index}",
                    left_table=left_table,
                    right_table=right_table,
                    left_col=left_col,
                    right_col=right_col,
                    type=join_type,
                    source_xml_ref=str(rel.get("source_xml_ref", "") or "").strip(),
                )
            )

        return joins
