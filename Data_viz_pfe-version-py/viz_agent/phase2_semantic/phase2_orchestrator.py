from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook, SemanticModel
from viz_agent.phase2_semantic.hybrid_semantic_layer import HybridSemanticLayer


@dataclass
class PhaseResult:
    phase: str
    ok: bool
    retry_hint: str = ""
    confidence: float = 0.0
    artifacts: Dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Phase2SemanticOrchestrator:
    """Entrypoint de la phase 2 pour isoler la logique semantique du pipeline global."""

    def __init__(self, llm_client=None) -> None:
        self.layer = HybridSemanticLayer(llm_client=llm_client)

    def run(self, workbook: ParsedWorkbook, intent: Dict[str, Any] | None = None) -> Tuple[SemanticModel, DataLineageSpec, Dict[str, Any]]:
        return self.layer.enrich_with_artifacts(workbook, intent)

    def run_with_result(
        self,
        workbook: ParsedWorkbook,
        intent: Dict[str, Any] | None = None,
    ) -> Tuple[SemanticModel | None, DataLineageSpec | None, Dict[str, Any], PhaseResult]:
        try:
            semantic_model, lineage, artifacts = self.run(workbook, intent)
            orchestration = artifacts.get("orchestration", {}) if isinstance(artifacts, dict) else {}
            confidence = float(orchestration.get("overall_confidence", 0.0) or 0.0)
            result = PhaseResult(
                phase="phase2_semantic",
                ok=True,
                retry_hint="",
                confidence=max(0.0, min(1.0, confidence)),
                artifacts={
                    "fact_table": getattr(semantic_model, "fact_table", ""),
                    "measure_count": len(getattr(semantic_model, "measures", []) or []),
                    "path": orchestration.get("selected_path", "unknown"),
                },
            )
            return semantic_model, lineage, artifacts, result
        except Exception as exc:
            result = PhaseResult(
                phase="phase2_semantic",
                ok=False,
                retry_hint="Verifier les cles API LLM et la connectivite; relancer avec cache semantic desactive.",
                confidence=0.0,
                artifacts={},
                errors=[str(exc)],
            )
            return None, None, {}, result
