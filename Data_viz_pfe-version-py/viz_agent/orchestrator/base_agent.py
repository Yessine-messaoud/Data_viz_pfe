from __future__ import annotations

from abc import ABC, abstractmethod

from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.pipeline_context import PipelineContext


class BaseAgent(ABC):
    """Base class for planner-driven modular agents."""

    name: str

    @abstractmethod
    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        raise NotImplementedError

    def _result(
        self,
        *,
        status: str,
        confidence: float,
        output: dict | None = None,
        errors: list[str] | None = None,
        retry_hint: str = "",
    ) -> PhaseAgentResult:
        return PhaseAgentResult(
            status=status,
            confidence=confidence,
            output=output or {},
            errors=errors or [],
            retry_hint=retry_hint,
        ).normalized()
