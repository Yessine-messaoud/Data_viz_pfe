from __future__ import annotations

from viz_agent.models.abstract_spec import SemanticModel


class SemanticMerger:
    def merge(self, schema_map, llm_enrichment) -> SemanticModel:
        entities = schema_map.tables
        measures = llm_enrichment.suggested_measures

        column_labels = getattr(llm_enrichment, "column_labels", {}) or {}
        column_roles = getattr(llm_enrichment, "column_roles", {}) or {}

        for table in entities:
            table_name = str(getattr(table, "name", ""))
            for column in getattr(table, "columns", []):
                key = f"{table_name}.{column.name}"
                if key in column_labels and column_labels[key]:
                    column.label = str(column_labels[key])
                if key in column_roles and column_roles[key] in {"measure", "dimension"}:
                    column.role = column_roles[key]

        dimensions = []
        for table in schema_map.tables:
            for col in table.columns:
                if col.role != "measure":
                    dimensions.append({"table": table.name, "column": col.name})

        return SemanticModel(
            entities=entities,
            measures=measures,
            dimensions=dimensions,
            hierarchies=llm_enrichment.hierarchies,
            relationships=[],
            glossary=[],
            fact_table="",
            grain="row",
        )
