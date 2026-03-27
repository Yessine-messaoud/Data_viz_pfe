from __future__ import annotations

from typing import Any, Dict, Tuple

from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook, SemanticModel
from viz_agent.phase2_semantic.hybrid_semantic_layer import HybridSemanticLayer


class Phase2SemanticOrchestrator:
    """Entrypoint de la phase 2 pour isoler la logique semantique du pipeline global."""

    def __init__(self, llm_client=None) -> None:
        self.layer = HybridSemanticLayer(llm_client=llm_client)

    def run(self, workbook: ParsedWorkbook, intent: Dict[str, Any] | None = None) -> Tuple[SemanticModel, DataLineageSpec, Dict[str, Any]]:
        return self.layer.enrich_with_artifacts(workbook, intent)
