from __future__ import annotations

from pathlib import Path

from viz_agent.orchestrator.agent_orchestrator import AgentOrchestrator
from viz_agent.orchestrator.agent_state import AgentState
from viz_agent.orchestrator.phase_agent import PhaseAgentResult


class _HighConfidenceAgent:
    name = "phase0"

    def execute(self, state: dict):
        return PhaseAgentResult(
            status="success",
            confidence=0.95,
            output={"ok": True, "phase": state.get("current_phase", "")},
        )


class _RetryThenSuccessAgent:
    name = "phase1"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, state: dict):
        self.calls += 1
        if self.calls == 1:
            return PhaseAgentResult(status="low_confidence", confidence=0.6, output={"step": "first"})
        return PhaseAgentResult(status="success", confidence=0.91, output={"step": "second"})


def test_agent_orchestrator_react_retry_and_trace(tmp_path: Path) -> None:
    trace_file = tmp_path / "agentic_trace.jsonl"
    snapshot_dir = tmp_path / "snapshots"

    orchestrator = AgentOrchestrator(max_retries=2, trace_file=trace_file, debug_snapshot_dir=snapshot_dir)
    orchestrator.register_tool(_HighConfidenceAgent())
    retry_agent = _RetryThenSuccessAgent()
    orchestrator.register_tool(retry_agent)

    state = AgentState(execution_id="exec-001")
    results = orchestrator.run(state, ["phase0", "phase1"])

    assert results["phase0"].status == "success"
    assert results["phase1"].status == "success"
    assert retry_agent.calls == 2
    assert state.react_history
    assert trace_file.exists()
    assert any(p.is_file() for p in snapshot_dir.glob("*.json"))


def test_agent_orchestrator_fails_after_max_retries(tmp_path: Path) -> None:
    class _AlwaysFailAgent:
        name = "phaseX"

        def execute(self, state: dict):
            return PhaseAgentResult(status="error", confidence=0.2, errors=["broken"])

    orchestrator = AgentOrchestrator(max_retries=1, trace_file=tmp_path / "trace.jsonl", debug_snapshot_dir=tmp_path / "snapshots")
    orchestrator.register_tool(_AlwaysFailAgent())

    state = AgentState(execution_id="exec-002")

    try:
        orchestrator.run(state, ["phaseX"])
        assert False, "Expected runtime error"
    except RuntimeError as exc:
        assert "failed" in str(exc).lower()
