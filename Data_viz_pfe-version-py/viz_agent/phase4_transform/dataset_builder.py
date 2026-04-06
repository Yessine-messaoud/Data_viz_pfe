from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any


@dataclass
class DatasetField:
    name: str
    source_field: str
    role: str
    rdl_type: str = "String"
    aggregation: str = ""
    expression: str = ""
    source_table: str = ""


@dataclass
class BuiltDataset:
    name: str
    source_name: str
    query: str
    fields: list[DatasetField] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    visual_ids: list[str] = field(default_factory=list)
    signature: str = ""


@dataclass
class DatasetBuildResult:
    datasets: list[dict[str, Any]] = field(default_factory=list)
    build_log: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    field_to_dataset: list[dict[str, str]] = field(default_factory=list)
    dataset_to_visual: list[dict[str, str]] = field(default_factory=list)
    expression_to_rdl_field: list[dict[str, str]] = field(default_factory=list)
    visual_assignments: dict[str, str] = field(default_factory=dict)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _field_name(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("column") or ref.get("name") or "").strip()
    return str(getattr(ref, "column", "") or getattr(ref, "name", "") or ref or "").strip()


def _field_table(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("table") or "").strip()
    return str(getattr(ref, "table", "") or "").strip()


def _semantic_entities(semantic_model: Any) -> list[Any]:
    if semantic_model is None:
        return []
    entities = getattr(semantic_model, "entities", None)
    if entities is not None:
        return list(entities)
    return list(_as_dict(semantic_model).get("entities", []) or [])


def _semantic_measures(semantic_model: Any) -> list[Any]:
    if semantic_model is None:
        return []
    measures = getattr(semantic_model, "measures", None)
    if measures is not None:
        return list(measures)
    return list(_as_dict(semantic_model).get("measures", []) or [])


def _semantic_columns(semantic_model: Any) -> list[tuple[str, str, str, str]]:
    columns: list[tuple[str, str, str, str]] = []
    for entity in _semantic_entities(semantic_model):
        entity_dict = _as_dict(entity)
        table_name = str(entity_dict.get("name") or getattr(entity, "name", "") or "").strip()
        for column in entity_dict.get("columns", []) or getattr(entity, "columns", []) or []:
            column_dict = _as_dict(column)
            column_name = str(column_dict.get("name") or getattr(column, "name", "") or "").strip()
            role = str(column_dict.get("role") or getattr(column, "role", "unknown") or "unknown").lower()
            pbi_type = str(column_dict.get("pbi_type") or getattr(column, "pbi_type", "text") or "text").lower()
            if column_name:
                columns.append((table_name, column_name, role, pbi_type))
    return columns


def _field_info(semantic_model: Any, field_name: str) -> tuple[str, str, str]:
    normalized = _normalize_text(field_name)
    for table_name, column_name, role, pbi_type in _semantic_columns(semantic_model):
        if _normalize_text(column_name) == normalized:
            return table_name, role, pbi_type
    for measure in _semantic_measures(semantic_model):
        measure_dict = _as_dict(measure)
        measure_name = str(measure_dict.get("name") or getattr(measure, "name", "") or "").strip()
        if _normalize_text(measure_name) == normalized:
            expression = str(measure_dict.get("expression") or getattr(measure, "expression", "") or "").strip()
            return "", "measure", "decimal" if any(token in expression.upper() for token in ("SUM(", "AVG(", "MIN(", "MAX(")) else "text"
    return "", "unknown", "text"


def _rdl_type_from_role(role: str, pbi_type: str) -> str:
    if role == "measure":
        if pbi_type in {"int64", "integer", "int", "long"}:
            return "Integer"
        return "Decimal"
    return "String"


def _infer_aggregation(field_name: str, pbi_type: str, measure_expression: str = "") -> str:
    expression = str(measure_expression or "").upper()
    if "COUNTD(" in expression or "COUNTDISTINCT(" in expression:
        return "CountDistinct"
    if "COUNT(" in expression or any(token in _normalize_text(field_name) for token in ("count", "qty", "quantity")):
        return "Count"
    if any(token in _normalize_text(field_name) for token in ("min",)):
        return "Min"
    if any(token in _normalize_text(field_name) for token in ("max",)):
        return "Max"
    if pbi_type in {"integer", "int64", "double", "decimal", "float", "number"}:
        return "Sum"
    return "Sum"


def _quote_identifier(value: str) -> str:
    return f"[{str(value).replace(']', ']]')}]"


class DatasetBuilder:
    def __init__(self) -> None:
        self.build_log: list[dict[str, Any]] = []
        self.warnings: list[str] = []

    def build(self, abstract_spec: dict[str, Any], semantic_model: Any, lineage: Any) -> DatasetBuildResult:
        result = DatasetBuildResult()
        visuals = self._extract_visuals(abstract_spec)
        lineage_tables = self._lineage_tables(lineage)
        fact_table = str(getattr(semantic_model, "fact_table", "") or _as_dict(semantic_model).get("fact_table", "") or "").strip()

        dataset_index: dict[str, BuiltDataset] = {}

        for visual in visuals:
            visual_id = str(visual.get("id") or visual.get("source_worksheet") or "visual").strip()
            visual_type = str(visual.get("type") or "table").strip().lower()
            binding = _as_dict(visual.get("data_binding"))
            axes = _as_dict(binding.get("axes"))

            dimensions: list[str] = []
            measures: list[str] = []
            source_candidates: list[str] = []

            for axis_name in ("x", "color", "detail", "group"):
                field = _field_name(axes.get(axis_name))
                if field:
                    _, role, _ = _field_info(semantic_model, field)
                    if role == "measure":
                        measures.append(field)
                    else:
                        dimensions.append(field)
                table = _field_table(axes.get(axis_name))
                if table:
                    source_candidates.append(table)

            for axis_name in ("y", "size"):
                field = _field_name(axes.get(axis_name))
                if field:
                    measures.append(field)
                table = _field_table(axes.get(axis_name))
                if table:
                    source_candidates.append(table)

            for field in binding.get("group_by", []) or []:
                field_name = str(field).strip()
                if field_name:
                    dimensions.append(field_name)

            dimensions = self._dedupe(dimensions)
            measures = self._dedupe(measures)

            source_name = self._resolve_source_name(source_candidates, fact_table, lineage_tables, semantic_model)
            if not source_name:
                self.warnings.append(f"{visual_id}: unable to resolve source table, skipped")
                continue

            if not dimensions and not measures:
                self.warnings.append(f"{visual_id}: no usable fields found, skipped")
                continue

            signature = self._signature(source_name, dimensions, measures, visual_type)
            if signature in dataset_index:
                dataset = dataset_index[signature]
                if visual_id not in dataset.visual_ids:
                    dataset.visual_ids.append(visual_id)
                result.visual_assignments[visual_id] = dataset.name
                result.dataset_to_visual.append({"dataset": dataset.name, "visual": visual_id})
                continue

            dataset_name = self._dataset_name(source_name, signature)
            built = self._build_dataset(source_name, dataset_name, visual_id, dimensions, measures, semantic_model)
            built.signature = signature
            dataset_index[signature] = built
            result.visual_assignments[visual_id] = built.name
            result.dataset_to_visual.append({"dataset": built.name, "visual": visual_id})

            for field in built.fields:
                result.field_to_dataset.append({"field": field.name, "dataset": built.name})
                if field.expression:
                    result.expression_to_rdl_field.append({"expression": field.expression, "rdl_field": field.name})

            result.build_log.append(
                {
                    "step": "dataset_creation",
                    "dataset": built.name,
                    "source": built.source_name,
                    "visual": visual_id,
                    "dimensions": built.group_by,
                    "measures": [field.name for field in built.fields if field.role == "measure"],
                    "status": "done",
                }
            )

        result.datasets = [self._dataset_to_dict(dataset) for dataset in dataset_index.values()]
        result.build_log.extend(self.build_log)
        result.warnings.extend(self.warnings)
        return result

    def _extract_visuals(self, abstract_spec: dict[str, Any]) -> list[dict[str, Any]]:
        dashboard = _as_dict(abstract_spec.get("dashboard_spec"))
        pages = dashboard.get("pages", []) or []
        visuals: list[dict[str, Any]] = []
        for page in pages:
            page_dict = _as_dict(page)
            for visual in page_dict.get("visuals", []) or []:
                visual_dict = _as_dict(visual)
                if visual_dict:
                    visual_dict.setdefault("page_id", page_dict.get("id", ""))
                    visual_dict.setdefault("page_name", page_dict.get("name", ""))
                    visuals.append(visual_dict)
        return visuals

    def _lineage_tables(self, lineage: Any) -> list[str]:
        lineage_dict = _as_dict(lineage)
        tables = lineage_dict.get("tables", []) if lineage_dict else getattr(lineage, "tables", []) or []
        names: list[str] = []
        for table in tables:
            table_dict = _as_dict(table)
            name = str(table_dict.get("name") or table_dict.get("id") or getattr(table, "name", "") or getattr(table, "id", "") or "").strip()
            if name:
                names.append(name)
        return self._dedupe(names)

    def _resolve_source_name(
        self,
        candidates: list[str],
        fact_table: str,
        lineage_tables: list[str],
        semantic_model: Any,
    ) -> str:
        for candidate in candidates:
            if candidate:
                return candidate
        if fact_table:
            return fact_table
        if lineage_tables:
            return lineage_tables[0]
        entities = _semantic_entities(semantic_model)
        if entities:
            first = _as_dict(entities[0])
            return str(first.get("name") or getattr(entities[0], "name", "") or "").strip()
        return ""

    def _dataset_name(self, source_name: str, signature: str) -> str:
        digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:8]
        return f"{_normalize_text(source_name) or 'dataset'}_{digest}"

    def _signature(self, source_name: str, dimensions: list[str], measures: list[str], visual_type: str) -> str:
        payload = "|".join(
            [
                _normalize_text(source_name),
                ",".join(sorted(_normalize_text(item) for item in dimensions)),
                ",".join(sorted(_normalize_text(item) for item in measures)),
                _normalize_text(visual_type),
            ]
        )
        return payload

    def _build_dataset(
        self,
        source_name: str,
        dataset_name: str,
        visual_id: str,
        dimensions: list[str],
        measures: list[str],
        semantic_model: Any,
    ) -> BuiltDataset:
        fields: list[DatasetField] = []
        select_items: list[str] = []
        group_by_items: list[str] = []

        for dimension in dimensions:
            table_name, role, pbi_type = _field_info(semantic_model, dimension)
            rdl_type = _rdl_type_from_role(role or "dimension", pbi_type)
            source_field = _quote_identifier(dimension)
            alias = _quote_identifier(dimension)
            select_items.append(f"{source_field} AS {alias}")
            group_by_items.append(source_field)
            fields.append(
                DatasetField(
                    name=dimension,
                    source_field=dimension,
                    role="dimension",
                    rdl_type=rdl_type,
                    aggregation="",
                    expression=f"=Fields!{dimension}.Value",
                    source_table=table_name or source_name,
                )
            )

        for measure in measures:
            table_name, role, pbi_type = _field_info(semantic_model, measure)
            semantic_measures = _semantic_measures(semantic_model)
            measure_expression = ""
            for semantic_measure in semantic_measures:
                semantic_dict = _as_dict(semantic_measure)
                measure_name = str(semantic_dict.get("name") or getattr(semantic_measure, "name", "") or "").strip()
                if _normalize_text(measure_name) == _normalize_text(measure):
                    measure_expression = str(semantic_dict.get("expression") or getattr(semantic_measure, "expression", "") or "")
                    break

            aggregation = _infer_aggregation(measure, pbi_type, measure_expression)
            source_field = _quote_identifier(measure)
            alias = _quote_identifier(measure)
            select_items.append(f"{aggregation.upper()}({source_field}) AS {alias}")
            rdl_type = _rdl_type_from_role("measure", pbi_type)
            fields.append(
                DatasetField(
                    name=measure,
                    source_field=measure,
                    role="measure",
                    rdl_type=rdl_type,
                    aggregation=aggregation,
                    expression=f"=Fields!{measure}.Value",
                    source_table=table_name or source_name,
                )
            )

        select_clause = ", ".join(select_items)
        if not select_clause:
            select_clause = "1 AS [StubValue]"
        query = f"SELECT {select_clause} FROM {_quote_identifier(source_name)}"
        if group_by_items and measures:
            query += f" GROUP BY {', '.join(group_by_items)}"

        built = BuiltDataset(
            name=dataset_name,
            source_name=source_name,
            query=query,
            fields=fields,
            group_by=self._dedupe(dimensions),
            visual_ids=[visual_id],
            signature=self._signature(source_name, dimensions, measures, "dataset"),
        )
        self.build_log.append(
            {
                "step": "aggregation_decision",
                "dataset": dataset_name,
                "group_by": built.group_by,
                "aggregations": [field.aggregation for field in fields if field.role == "measure"],
                "status": "done",
            }
        )
        return built

    def _dataset_to_dict(self, dataset: BuiltDataset) -> dict[str, Any]:
        return {
            "name": dataset.name,
            "source_name": dataset.source_name,
            "query": dataset.query,
            "fields": [field.__dict__.copy() for field in dataset.fields],
            "group_by": list(dataset.group_by),
            "visual_ids": list(dataset.visual_ids),
            "signature": dataset.signature,
        }

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = _normalize_text(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(str(value).strip())
        return ordered
