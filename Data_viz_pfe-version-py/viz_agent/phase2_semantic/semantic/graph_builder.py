from __future__ import annotations

from typing import Any


def _safe_id(prefix: str, value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-", ":", "."} else "_" for ch in str(value))
    return f"{prefix}:{safe}"


def _column_lookup(lineage) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for table in getattr(lineage, "tables", []) or []:
        tname = str(getattr(table, "name", "") or "").strip()
        for col in getattr(table, "columns", []) or []:
            cname = str(getattr(col, "name", "") or "").strip()
            if not tname or not cname:
                continue
            lookup[f"{tname}.{cname}".lower()] = {
                "table": tname,
                "column": cname,
                "role": str(getattr(col, "role", "unknown") or "unknown").lower(),
                "type": str(getattr(col, "pbi_type", "text") or "text"),
            }
    return lookup


def _visual_fields(worksheet) -> list[tuple[str, str, str]]:
    fields: list[tuple[str, str, str]] = []
    for shelf_name in ("rows_shelf", "cols_shelf", "marks_shelf"):
        for item in getattr(worksheet, shelf_name, []) or []:
            table = str(getattr(item, "table", "") or "").strip()
            column = str(getattr(item, "column", "") or "").strip()
            if table and column:
                fields.append((table, column, shelf_name))
    return fields


def _looks_measure_name(name: str) -> bool:
    lowered = name.lower()
    keywords = ("amount", "sales", "revenue", "profit", "cost", "price", "qty", "quantity", "count", "sum", "avg")
    return any(keyword in lowered for keyword in keywords)


def _semantic_measure_lookup(semantic_model) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for measure in getattr(semantic_model, "measures", []) or []:
        mname = str(getattr(measure, "name", "") or "").strip()
        mexpr = str(getattr(measure, "tableau_expression", "") or "").strip()
        if mexpr:
            lookup[mexpr.lower()] = mname
        if mname:
            lookup[mname.lower()] = mname
    return lookup


class SemanticGraphBuilder:
    @classmethod
    def build(cls, semantic_model, lineage, workbook, mappings: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        rels: list[dict[str, Any]] = []

        colmap = _column_lookup(lineage)

        for table in getattr(lineage, "tables", []) or []:
            tname = str(getattr(table, "name", "") or "").strip()
            if not tname:
                continue
            tid = _safe_id("table", tname)
            nodes.append({"id": tid, "type": "Table", "name": tname, "schema": str(getattr(table, "schema", "dbo"))})

            for col in getattr(table, "columns", []) or []:
                cname = str(getattr(col, "name", "") or "").strip()
                if not cname:
                    continue
                cid = _safe_id("column", f"{tname}.{cname}")
                role = str(getattr(col, "role", "unknown") or "unknown").lower()
                nodes.append(
                    {
                        "id": cid,
                        "type": "Column",
                        "name": cname,
                        "table": tname,
                        "role": role,
                        "pbi_type": str(getattr(col, "pbi_type", "text") or "text"),
                    }
                )
                rels.append({"source_id": tid, "target_id": cid, "type": "HAS_COLUMN"})

                if role == "dimension":
                    did = _safe_id("dimension", f"{tname}.{cname}")
                    nodes.append({"id": did, "type": "Dimension", "name": cname, "table": tname})
                    rels.append({"source_id": cid, "target_id": did, "type": "IS_DIMENSION"})

                if role == "measure":
                    mid = _safe_id("measure", f"{tname}.{cname}")
                    nodes.append({"id": mid, "type": "Measure", "name": cname, "expression": f"SUM([{cname}])"})
                    rels.append({"source_id": cid, "target_id": mid, "type": "IS_MEASURE"})
                    rels.append({"source_id": cid, "target_id": mid, "type": "AGGREGATED_AS", "agg": "SUM"})

        for measure in getattr(semantic_model, "measures", []) or []:
            mname = str(getattr(measure, "name", "") or "").strip()
            if not mname:
                continue
            mid = _safe_id("measure", mname)
            nodes.append(
                {
                    "id": mid,
                    "type": "Measure",
                    "name": mname,
                    "expression": str(getattr(measure, "expression", "") or ""),
                }
            )
            for src in getattr(measure, "source_columns", []) or []:
                table = str(getattr(src, "table", "") or "").strip()
                col = str(getattr(src, "column", "") or "").strip()
                if not table or not col:
                    continue
                cid = _safe_id("column", f"{table}.{col}")
                rels.append({"source_id": cid, "target_id": mid, "type": "AGGREGATED_AS", "agg": "CUSTOM"})

        semantic_measure_names = _semantic_measure_lookup(semantic_model)

        for worksheet in getattr(workbook, "worksheets", []) or []:
            wname = str(getattr(worksheet, "name", "") or "").strip()
            mark = str(getattr(worksheet, "mark_type", "unknown") or "unknown").strip().lower()
            if not wname:
                continue
            vid = _safe_id("visual", wname)
            nodes.append({"id": vid, "type": "Visual", "name": wname, "subtype": mark})

            for table, column, shelf_name in _visual_fields(worksheet):
                key = f"{table}.{column}".lower()
                col_meta = colmap.get(key, {})
                role = str(col_meta.get("role", "unknown"))
                cid = _safe_id("column", f"{table}.{column}")

                inferred_measure = False
                if role == "unknown":
                    inferred_measure = column.lower() in semantic_measure_names or _looks_measure_name(column)

                if shelf_name == "marks_shelf" and (role == "measure" or inferred_measure):
                    measure_name = semantic_measure_names.get(column.lower(), f"{table}.{column}")
                    mid = _safe_id("measure", measure_name)
                    nodes.append({"id": mid, "type": "Measure", "name": measure_name, "expression": f"SUM([{column}])"})
                    rels.append({"source_id": cid, "target_id": mid, "type": "IS_MEASURE"})
                    rels.append({"source_id": mid, "target_id": vid, "type": "USED_IN"})
                    continue

                did = _safe_id("dimension", f"{table}.{column}")
                nodes.append({"id": did, "type": "Dimension", "name": column, "table": table})
                rels.append({"source_id": cid, "target_id": did, "type": "IS_DIMENSION"})
                rels.append({"source_id": did, "target_id": vid, "type": "GROUPED_BY"})

        for mapping in mappings or []:
            col_name = str(mapping.get("column", "") or "").strip()
            term = str(mapping.get("mapped_business_term", "") or "").strip()
            if not col_name or not term:
                continue
            term_id = _safe_id("term", term)
            nodes.append({"id": term_id, "type": "BusinessTerm", "name": term})

            target_column = None
            for key, value in colmap.items():
                _ = key
                if str(value.get("column", "")).lower() == col_name.lower():
                    target_column = f"{value['table']}.{value['column']}"
                    break
            if target_column:
                cid = _safe_id("column", target_column)
                rels.append(
                    {
                        "source_id": cid,
                        "target_id": term_id,
                        "type": "MAPPED_TO",
                        "confidence": float(mapping.get("confidence", 0.0) or 0.0),
                        "method": str(mapping.get("method", "unknown")),
                    }
                )

        uniq_nodes: dict[str, dict[str, Any]] = {}
        for node in nodes:
            node_id = str(node.get("id", "") or "")
            if not node_id:
                continue
            if node_id in uniq_nodes:
                uniq_nodes[node_id].update(node)
            else:
                uniq_nodes[node_id] = node

        uniq_rels: dict[str, dict[str, Any]] = {}
        for rel in rels:
            key = f"{rel.get('source_id')}|{rel.get('type')}|{rel.get('target_id')}"
            uniq_rels[key] = rel

        payload = {"nodes": list(uniq_nodes.values()), "relationships": list(uniq_rels.values())}
        validate_graph_payload(payload)
        return payload


def validate_graph_payload(payload: dict[str, Any]) -> None:
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    if not isinstance(nodes, list):
        raise ValueError("Invalid graph payload: nodes must be a list")

    type_counts: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", "") or "")
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    measures = type_counts.get("Measure", 0)
    dimensions = type_counts.get("Dimension", 0)
    visuals = type_counts.get("Visual", 0)

    if measures < 1 or dimensions < 1 or visuals < 1:
        raise ValueError(
            "Semantic graph validation failed: requires at least 1 Measure, 1 Dimension, and 1 Visual node"
        )

    non_basic = sum(count for node_type, count in type_counts.items() if node_type not in {"Table", "Column"})
    if non_basic == 0:
        raise ValueError("Semantic graph validation failed: graph only contains Table/Column nodes")
