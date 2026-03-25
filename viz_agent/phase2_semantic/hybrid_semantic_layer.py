from __future__ import annotations

from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook
from viz_agent.phase2_semantic.fact_table_detector import detect_fact_table, filter_fk_measures
from viz_agent.phase2_semantic.join_resolver import JoinResolver
from viz_agent.phase2_semantic.schema_mapper import TableauSchemaMapper
from viz_agent.phase2_semantic.semantic_enricher import SemanticEnricher
from viz_agent.phase2_semantic.semantic_merger import SemanticMerger


class HybridSemanticLayer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def enrich(self, workbook: ParsedWorkbook, intent=None):
        schema_map = TableauSchemaMapper().map(workbook)
        joins = JoinResolver().resolve(workbook.datasources)

        llm_enrichment = SemanticEnricher(self.llm_client).enrich(workbook, schema_map)

        semantic_model = SemanticMerger().merge(schema_map, llm_enrichment)
        semantic_model.fact_table = detect_fact_table(schema_map.tables, joins)
        semantic_model.measures = filter_fk_measures(semantic_model.measures)

        lineage = DataLineageSpec(
            tables=schema_map.tables,
            joins=joins,
            columns_used=[],
        )

        return semantic_model, lineage
