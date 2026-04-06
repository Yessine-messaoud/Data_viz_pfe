from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass
class PipelineContext:
    """Shared context passed across planner-managed agents."""

    input_data: dict[str, Any] = field(default_factory=dict)
    semantic_model: dict[str, Any] = field(default_factory=dict)
    abstract_spec: dict[str, Any] = field(default_factory=dict)
    tool_model: dict[str, Any] = field(default_factory=dict)
    rdl_output: dict[str, Any] = field(default_factory=dict)
    confidence_scores: dict[str, float] = field(default_factory=dict)
    error_logs: list[dict[str, Any]] = field(default_factory=list)

    # Compatibility payloads with existing orchestrator state contract.
    runtime_context: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    previous_outputs: dict[str, Any] = field(default_factory=dict)
    execution_id: str = ""
    current_phase: str = ""
    confidence_history: list[dict[str, Any]] = field(default_factory=list)
    react_history: list[dict[str, Any]] = field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "current_phase": self.current_phase,
            "context": self.runtime_context,
            "artifacts": self.artifacts,
            "previous_outputs": self.previous_outputs,
            "confidence_history": self.confidence_history,
            "react_history": self.react_history,
        }

    def set_phase(self, phase_name: str) -> None:
        self.current_phase = str(phase_name)

    def record_confidence(self, phase_name: str, confidence: float, status: str) -> None:
        self.confidence_history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": str(phase_name),
                "confidence": max(0.0, min(1.0, float(confidence))),
                "status": str(status),
            }
        )

    def add_react_event(self, thought: str, action: str, observation: str, phase_name: str, attempt: int) -> None:
        self.react_history.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "phase": str(phase_name),
                "attempt": int(attempt),
                "thought": str(thought),
                "action": str(action),
                "observation": str(observation),
            }
        )

    def snapshot(self, snapshot_dir: Path, label: str) -> Path:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path = snapshot_dir / f"{label}_{ts}.json"
        path.write_text(json.dumps(self.to_state_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
        return path

    def update_from_phase_result(self, phase_name: str, output: dict[str, Any], confidence: float) -> None:
        self.previous_outputs[phase_name] = dict(output or {})
        self.confidence_scores[phase_name] = max(0.0, min(1.0, float(confidence)))

        if phase_name == "semantic_reasoning":
            self.semantic_model = dict(output.get("semantic_graph", {}))
        elif phase_name == "specification":
            self.abstract_spec = dict(output.get("abstract_spec", {}))
        elif phase_name == "transformation":
            self.tool_model = dict(output.get("tool_model", {}))
        elif phase_name == "export":
            self.rdl_output = dict(output.get("export_result", {}))

    def add_error(self, phase_name: str, message: str) -> None:
        self.error_logs.append({"phase": phase_name, "message": str(message)})
