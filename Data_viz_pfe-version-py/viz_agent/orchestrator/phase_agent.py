from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class PhaseAgentResult:
    """Standard result envelope returned by every phase agent tool."""

    status: str
    confidence: float
    output: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    retry_hint: str = ""

    def normalized(self) -> "PhaseAgentResult":
        safe_conf = max(0.0, min(1.0, float(self.confidence)))
        safe_status = str(self.status or "error").lower()
        if safe_status not in {"success", "error", "low_confidence"}:
            safe_status = "error"
        return PhaseAgentResult(
            status=safe_status,
            confidence=safe_conf,
            output=dict(self.output or {}),
            errors=[str(e) for e in (self.errors or [])],
            retry_hint=str(self.retry_hint or ""),
        )


class PhaseAgent(Protocol):
    """Contract for any phase agent used as a tool by the central orchestrator."""

    name: str

    def execute(self, state: dict[str, Any]) -> PhaseAgentResult:
        ...
