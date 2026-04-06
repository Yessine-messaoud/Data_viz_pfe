from __future__ import annotations

from viz_agent.models.abstract_spec import ParsedWorkbook
from viz_agent.phase2_semantic.agentic_semantic_orchestrator import AgenticSemanticOrchestrator


class HybridSemanticLayer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.orchestrator = AgenticSemanticOrchestrator(llm_client=llm_client)

    def enrich(self, workbook: ParsedWorkbook, intent=None):
        semantic_model, lineage, _ = self.enrich_with_artifacts(workbook, intent)
        return semantic_model, lineage

    def enrich_with_artifacts(self, workbook: ParsedWorkbook, intent=None):
        return self.orchestrator.run(workbook, intent)
