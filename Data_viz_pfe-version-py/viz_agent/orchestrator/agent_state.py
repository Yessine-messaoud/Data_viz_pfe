from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


@dataclass
class AgentState:
    """Shared mutable state for agentic orchestration runs."""

    execution_id: str
    current_phase: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    previous_outputs: dict[str, Any] = field(default_factory=dict)
    errors_history: list[dict[str, Any]] = field(default_factory=list)
    confidence_history: list[dict[str, Any]] = field(default_factory=list)
    react_history: list[dict[str, Any]] = field(default_factory=list)

    def set_phase(self, phase_name: str) -> None:
        self.current_phase = phase_name

    def record_output(self, phase_name: str, output: dict[str, Any]) -> None:
        self.previous_outputs[phase_name] = dict(output or {})

    def record_error(self, phase_name: str, error: str, attempt: int) -> None:
        self.errors_history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": phase_name,
                "attempt": attempt,
                "error": str(error),
            }
        )

    def record_confidence(self, phase_name: str, confidence: float, status: str) -> None:
        self.confidence_history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": phase_name,
                "confidence": max(0.0, min(1.0, float(confidence))),
                "status": status,
            }
        )

    def add_react_event(self, thought: str, action: str, observation: str, phase_name: str, attempt: int) -> None:
        self.react_history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": phase_name,
                "attempt": attempt,
                "thought": thought,
                "action": action,
                "observation": observation,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "current_phase": self.current_phase,
            "context": self.context,
            "artifacts": self.artifacts,
            "previous_outputs": self.previous_outputs,
            "errors_history": self.errors_history,
            "confidence_history": self.confidence_history,
            "react_history": self.react_history,
        }

    def snapshot(self, snapshot_dir: Path, label: str) -> Path:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path = snapshot_dir / f"{label}_{ts}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
