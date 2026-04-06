from __future__ import annotations

import pandas as pd

from viz_agent.models.abstract_spec import ColumnDef, ParsedWorkbook, TableRef
from viz_agent.phase0_extraction.registry.logical_name_registry import LogicalNameRegistry


class TableauSchemaMapper:
    @staticmethod
    def _pandas_dtype_to_pbi_type(dtype: object) -> str:
        if pd.api.types.is_bool_dtype(dtype):
            return "boolean"
        if pd.api.types.is_integer_dtype(dtype):
            return "int64"
        if pd.api.types.is_float_dtype(dtype):
            return "decimal"
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "dateTime"
        return "text"

    @staticmethod
    def _merge_table(tables_by_name: dict[str, TableRef], candidate: TableRef) -> None:
        key = str(candidate.name or "").strip()
        if not key:
            return

        existing = tables_by_name.get(key)
        if existing is None:
            tables_by_name[key] = candidate
            return

        seen_cols = {str(col.name).lower() for col in existing.columns}
        for col in candidate.columns:
            cname = str(col.name or "").strip()
            if not cname:
                continue
            norm = cname.lower()
            if norm in seen_cols:
                continue
            existing.columns.append(col)
            seen_cols.add(norm)

        existing.row_count = max(int(existing.row_count or 0), int(candidate.row_count or 0))
        if not getattr(existing, "source_name", "") and getattr(candidate, "source_name", ""):
            existing.source_name = candidate.source_name

    def map(self, workbook: ParsedWorkbook):
        tables_by_name: dict[str, TableRef] = {}
        naming = LogicalNameRegistry()

        registry = workbook.data_registry
        if registry is not None and hasattr(registry, "all_frames"):
            frames = registry.all_frames()
            for physical_name, dataframe in frames.items():
                logical_name = naming.resolve(str(physical_name), "")
                columns = [
                    ColumnDef(
                        name=str(column),
                        pbi_type=TableauSchemaMapper._pandas_dtype_to_pbi_type(dataframe[column].dtype),
                        role="measure" if str(dataframe[column].dtype) in ("int64", "float64") else "dimension",
                    )
                    for column in dataframe.columns
                ]
                self._merge_table(
                    tables_by_name,
                    TableRef(
                        id=str(physical_name),
                        name=logical_name,
                        source_name=str(physical_name),
                        columns=columns,
                        row_count=len(dataframe),
                    ),
                )

        if not tables_by_name:
            for datasource in workbook.datasources:
                physical_name = str(datasource.name or datasource.caption or "")
                logical_name = naming.resolve(physical_name, str(datasource.caption or ""))
                self._merge_table(
                    tables_by_name,
                    TableRef(
                        id=physical_name or logical_name,
                        name=logical_name,
                        source_name=physical_name or logical_name,
                        columns=datasource.columns,
                    ),
                )

        tables = list(tables_by_name.values())

        class SchemaMap:
            def __init__(self, tables_, physical_to_logical_):
                self.tables = tables_
                self.physical_to_logical = physical_to_logical_

        return SchemaMap(tables, naming.mapping)
