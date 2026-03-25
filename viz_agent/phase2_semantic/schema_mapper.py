from __future__ import annotations

from viz_agent.models.abstract_spec import ColumnDef, ParsedWorkbook, TableRef


class TableauSchemaMapper:
    def map(self, workbook: ParsedWorkbook):
        tables = []

        registry = workbook.data_registry
        if registry is not None and hasattr(registry, "all_frames"):
            frames = registry.all_frames()
            for table_name, dataframe in frames.items():
                columns = [
                    ColumnDef(
                        name=str(column),
                        role="measure" if str(dataframe[column].dtype) in ("int64", "float64") else "dimension",
                    )
                    for column in dataframe.columns
                ]
                tables.append(
                    TableRef(
                        id=str(table_name),
                        name=str(table_name),
                        columns=columns,
                        row_count=len(dataframe),
                    )
                )

        if not tables:
            for datasource in workbook.datasources:
                tables.append(
                    TableRef(
                        id=datasource.name or datasource.caption,
                        name=datasource.name or datasource.caption,
                        columns=datasource.columns,
                    )
                )

        class SchemaMap:
            def __init__(self, tables_):
                self.tables = tables_

        return SchemaMap(tables)
