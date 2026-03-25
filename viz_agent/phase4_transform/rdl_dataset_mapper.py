from __future__ import annotations

from dataclasses import dataclass

from viz_agent.models.abstract_spec import DataLineageSpec
from viz_agent.phase0_data.data_source_registry import DataSourceRegistry


@dataclass
class RDLField:
    name: str
    data_field: str
    rdl_type: str


@dataclass
class RDLDataset:
    name: str
    query: str
    connection_ref: str
    fields: list[RDLField]


PBI_TO_RDL_TYPE = {
    "text": "String",
    "int64": "Integer",
    "double": "Float",
    "decimal": "Float",
    "dateTime": "DateTime",
    "date": "DateTime",
    "boolean": "Boolean",
}


class RDLDatasetMapper:
    @staticmethod
    def build(registry: DataSourceRegistry, lineage: DataLineageSpec) -> list[RDLDataset]:
        datasets: list[RDLDataset] = []
        for table_ref in lineage.tables:
            fields = [
                RDLField(
                    name=col.name,
                    data_field=col.name,
                    rdl_type=PBI_TO_RDL_TYPE.get(col.pbi_type, "String"),
                )
                for col in table_ref.columns
            ]
            datasets.append(
                RDLDataset(
                    name=table_ref.name,
                    query=registry.get_sql_query(table_ref.name),
                    connection_ref="DataSource1",
                    fields=fields,
                )
            )
        return datasets
