from __future__ import annotations

import asyncio

from viz_agent.orchestrator.agentic_orchestrator import OrchestratorAgent
from viz_agent.orchestrator.models import ExecutionContext, ExecutionStatus, PipelineDefinition


class _FlakyAgent:
    def __init__(self):
        self.calls = 0

    def run(self, _step):
        self.calls += 1
        if self.calls == 1:
            return {"validation_status": "failed", "error": "synthetic validation failure"}
        return {"validation_status": "passed", "content": "ok"}


def test_self_heal_returns_repaired_result() -> None:
    orchestrator = OrchestratorAgent(config={})
    context = ExecutionContext(
        execution_id="exec-1",
        intent={},
        context={},
        artifacts={},
    )

    orchestrator._run_step = lambda _step, _ctx: {"validation_status": "passed", "content": "fixed"}  # type: ignore[attr-defined]
    repaired = orchestrator.self_heal(
        step={"name": "export", "agent": "export", "inputs": {}},
        result={"validation_status": "failed"},
        context=context,
    )

    assert repaired is not None
    assert repaired["self_healed"] is True
    assert repaired["validation_status"] == "passed"


def test_execute_pipeline_applies_partial_rerun_after_validation_failure() -> None:
    orchestrator = OrchestratorAgent(config={"max_retries": 2})
    flaky_agent = _FlakyAgent()
    orchestrator.agent_factory.get_agent = lambda _name: flaky_agent  # type: ignore[method-assign]

    context = ExecutionContext(
        execution_id="exec-2",
        intent={"type": "conversion"},
        context={},
        artifacts={"source_path": "dummy.twbx"},
    )
    pipeline = PipelineDefinition(
        pipeline_id="p1",
        steps=[{"name": "export", "agent": "export", "required": True, "inputs": {}}],
        parallel_groups=[],
        error_handling={},
        validation_points=["export"],
    )

    result = asyncio.run(orchestrator._execute_pipeline(pipeline, context))

    assert result.status == ExecutionStatus.COMPLETED
    assert result.retries >= 1
    assert result.results["export"]["self_healed"] is True
