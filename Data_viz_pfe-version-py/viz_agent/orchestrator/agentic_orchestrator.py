from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from .agent_factory import AgentFactory
from .error_handler import ErrorHandler, RecoveryAction
from .models import ExecutionContext, ExecutionResult, ExecutionStatus, PipelineDefinition
from .pipeline_builder import PipelineBuilder
from .pipeline_validator import PipelineValidator


class OrchestratorAgent:
    """
    Agent orchestrateur principal.
    Coordonne l'execution du pipeline avec validation continue et self-healing cible.
    """

    def __init__(self, config: Dict[str, Any], phases: List[Any] | None = None):
        self.config = config
        self.logger = logging.getLogger("OrchestratorAgent")
        self.pipeline_builder = PipelineBuilder(config.get("pipeline", {}))
        self.agent_factory = AgentFactory(config.get("agents", {}))
        self.error_handler = ErrorHandler(config.get("error_handling", {}))
        self.validator = PipelineValidator(config.get("validation", {}))
        self.execution_history: List[ExecutionResult] = []
        self.metrics = {"executions": 0, "successful": 0, "failed": 0, "retries": 0, "avg_duration_ms": 0}

        # Observabilite agentique
        self.validation_agent = GlobalValidationAgent()
        self.lineage_agent = LineageAgent()
        self.correction_logger = CorrectionLogger()
        self.monitoring_agent = MonitoringAgent()
        self.phases = phases or []

    async def orchestrate(self, intent: Dict[str, Any], context: Dict[str, Any], artifacts: Dict[str, Any]) -> ExecutionResult:
        execution_id = self._generate_execution_id()
        self.metrics["executions"] += 1
        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info("Starting orchestration %s - intent=%s", execution_id, intent.get("type"))
            exec_context = ExecutionContext(
                execution_id=execution_id,
                intent=intent,
                context=context,
                artifacts=artifacts,
            )
            pipeline = self.pipeline_builder.build(intent, context, artifacts)
            validation = self.validator.validate_pipeline(pipeline, exec_context)
            if not validation.is_valid:
                self.logger.warning("Pipeline validation issues: %s", validation.issues)
                pipeline = self._auto_correct_pipeline(pipeline, validation)

            self.validation_agent.validate(pipeline, exec_context)
            self.lineage_agent.capture({"kind": "pipeline", "pipeline_id": pipeline.pipeline_id})
            self.monitoring_agent.track({"kind": "pipeline_start", "pipeline_id": pipeline.pipeline_id})

            result = await self._execute_pipeline(pipeline, exec_context)
            result.duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            self._update_metrics(result)
            self.execution_history.append(result)
            return result
        except Exception as exc:
            self.logger.exception("Orchestration failed: %s", exc)
            self.metrics["failed"] += 1
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                pipeline=PipelineDefinition(
                    pipeline_id="error",
                    steps=[],
                    parallel_groups=[],
                    error_handling={},
                    validation_points=[],
                ),
                results={},
                errors=[{"error": str(exc)}],
                duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                retries=0,
                validation_issues=[],
            )

    async def _execute_pipeline(self, pipeline: PipelineDefinition, context: ExecutionContext) -> ExecutionResult:
        results: Dict[str, Any] = {}
        errors: List[Dict[str, Any]] = []
        validation_issues: List[Dict[str, Any]] = []
        retries = 0
        max_retries = int(self.config.get("max_retries", 3))

        for step in pipeline.steps:
            step_name = step.get("name", "unknown_step")
            retry_count = 0
            completed = False

            while not completed:
                try:
                    self.validation_agent.validate(step, context)
                    self.lineage_agent.capture({"kind": "step_start", "step": step_name})
                    self.monitoring_agent.track({"kind": "step_start", "step": step_name})
                    self.correction_logger.track_decision({"step": step_name, "decision": "run"})

                    step_result = self._run_step(step, context)
                    step_result = step_result if isinstance(step_result, dict) else {"value": step_result}
                    results[step_name] = step_result

                    issues = self.validation_agent.validate(step_result, context).get("issues", [])
                    validation_issues.extend(issues)
                    step_failed = self._step_failed(step_result, issues)

                    if step_failed:
                        self.correction_logger.log_issue(
                            {"step": step_name, "error_type": "validation", "result": step_result, "issues": issues}
                        )
                        healed = self.self_heal(step, step_result, context)
                        if healed is not None:
                            retries += 1
                            retry_count += 1
                            results[step_name] = healed
                            self.correction_logger.track_decision(
                                {"step": step_name, "decision": "self_heal_success", "retry_count": retry_count}
                            )
                            completed = True
                            continue

                        raise RuntimeError(f"Validation failed for step {step_name}")

                    self.lineage_agent.capture({"kind": "step_end", "step": step_name, "status": "ok"})
                    self.monitoring_agent.track({"kind": "step_end", "step": step_name, "status": "ok"})
                    completed = True
                except Exception as exc:
                    recovery = self.error_handler.handle_error(exc, step, context, retry_count)
                    errors.append({"step": step_name, "error": str(exc), "recovery": recovery.value})
                    self.correction_logger.track_decision(
                        {"step": step_name, "decision": "error", "recovery": recovery.value, "error": str(exc)}
                    )

                    if recovery == RecoveryAction.RETRY and retry_count < max_retries:
                        retry_count += 1
                        retries += 1
                        continue
                    if recovery == RecoveryAction.SKIP:
                        completed = True
                        break
                    if recovery == RecoveryAction.FALLBACK:
                        fallback_result = {"step": step_name, "fallback_used": True, "validation_status": "passed"}
                        results[step_name] = fallback_result
                        completed = True
                        break
                    # ABORT / RECONFIGURE not implemented as automatic re-plan yet.
                    return ExecutionResult(
                        execution_id=context.execution_id,
                        status=ExecutionStatus.FAILED,
                        pipeline=pipeline,
                        results=results,
                        errors=errors,
                        duration_ms=0,
                        retries=retries,
                        validation_issues=validation_issues,
                    )

        status = ExecutionStatus.COMPLETED if not errors else ExecutionStatus.PARTIAL
        return ExecutionResult(
            execution_id=context.execution_id,
            status=status,
            pipeline=pipeline,
            results=results,
            errors=errors,
            duration_ms=0,
            retries=retries,
            validation_issues=validation_issues,
        )

    def _run_step(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        agent_key = step.get("agent") or step.get("name")
        agent = self.agent_factory.get_agent(agent_key)

        step_payload = copy.deepcopy(step)
        step_payload.setdefault("inputs", {})
        step_payload["inputs"].setdefault("context", context.context)
        step_payload["inputs"].setdefault("artifacts", context.artifacts)
        step_payload["inputs"].setdefault("execution_id", context.execution_id)

        if hasattr(agent, "run"):
            return agent.run(step_payload)
        if hasattr(agent, "execute"):
            return agent.execute(step_payload)
        raise AttributeError(f"Agent '{agent_key}' has no 'run' or 'execute' method")

    def _step_failed(self, step_result: Dict[str, Any], issues: List[Dict[str, Any]]) -> bool:
        if step_result.get("validation_status") == "failed":
            return True
        if step_result.get("error"):
            return True
        return any(issue.get("severity") == "error" for issue in issues if isinstance(issue, dict))

    def _generate_execution_id(self) -> str:
        return str(uuid.uuid4())

    def _auto_correct_pipeline(self, pipeline: PipelineDefinition, validation: Any) -> PipelineDefinition:
        # Ensure final export/validation step remains mandatory.
        step_names = [step.get("name") for step in pipeline.steps]
        if "export" not in step_names:
            pipeline.steps.append({"name": "export", "agent": "export", "required": True, "inputs": {}})
        return pipeline

    def _update_metrics(self, result: ExecutionResult) -> None:
        if result.status == ExecutionStatus.COMPLETED:
            self.metrics["successful"] += 1
        elif result.status in {ExecutionStatus.FAILED, ExecutionStatus.PARTIAL}:
            self.metrics["failed"] += 1
        self.metrics["retries"] += result.retries

        executions = max(1, self.metrics["executions"])
        current_avg = self.metrics["avg_duration_ms"]
        self.metrics["avg_duration_ms"] = int(((current_avg * (executions - 1)) + result.duration_ms) / executions)

    def self_heal(self, step: Dict[str, Any], result: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any] | None:
        """
        Apply targeted correction and perform partial re-execution for the faulty step.
        """
        fix_payload = self.correction_logger.auto_fix(result, step)
        if not fix_payload:
            return None

        repaired_step = copy.deepcopy(step)
        repaired_step.setdefault("inputs", {})
        repaired_step["inputs"]["repair_payload"] = fix_payload
        repaired_step["inputs"]["previous_result"] = result
        repaired_step["inputs"]["self_heal"] = True

        try:
            rerun_result = self._run_step(repaired_step, context)
        except Exception as exc:
            self.correction_logger.log_issue(
                {"step": step.get("name"), "error_type": "self_heal_execution", "error": str(exc)}
            )
            return None

        rerun_result = rerun_result if isinstance(rerun_result, dict) else {"value": rerun_result}
        rerun_result.setdefault("validation_status", "passed")
        rerun_result["self_healed"] = True
        rerun_result["self_heal_strategy"] = fix_payload.get("strategy", "retry")
        return rerun_result


class GlobalValidationAgent:
    def validate(self, *artifacts) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        for artifact in artifacts:
            if isinstance(artifact, dict):
                if artifact.get("validation_status") == "failed":
                    issues.append(
                        {
                            "severity": "error",
                            "code": "GVAL_001",
                            "message": "Artifact reported validation_status=failed",
                        }
                    )
                if artifact.get("error"):
                    issues.append(
                        {
                            "severity": "error",
                            "code": "GVAL_002",
                            "message": f"Artifact error: {artifact.get('error')}",
                        }
                    )
        score = 1.0 if not issues else max(0.0, 1.0 - 0.2 * len(issues))
        return {"global_score": score, "issues": issues}


class LineageAgent:
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []

    def capture(self, artifact: Dict[str, Any]):
        self.entries.append({"timestamp": datetime.now(timezone.utc).isoformat(), "artifact": artifact})


class CorrectionLogger:
    def __init__(self):
        self.corrections: List[Dict[str, Any]] = []
        self.decisions: List[Dict[str, Any]] = []

    def log_issue(self, issue: Dict[str, Any]):
        self.corrections.append(issue)

    def auto_fix(self, result: Dict[str, Any], step: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
        """
        Heuristic self-healing decisions.
        Returns a fix payload when a partial rerun should be attempted.
        """
        if not isinstance(result, dict):
            return {"strategy": "retry_non_dict_result"}

        if result.get("validation_status") == "failed":
            return {"strategy": "retry_after_validation_failure"}

        if result.get("error"):
            return {"strategy": "retry_after_error_key"}

        # Recovery hint from step metadata.
        if step and step.get("required", True):
            return {"strategy": "retry_required_step"}

        return None

    def track_decision(self, result: Dict[str, Any]):
        self.decisions.append(result)


class MonitoringAgent:
    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []

    def track(self, artifact: Dict[str, Any]):
        self.metrics.append({"timestamp": datetime.now(timezone.utc).isoformat(), "artifact": artifact})


class Orchestrator:
    """
    Legacy wrapper kept for compatibility with previous integration points.
    """

    def __init__(self, phases: List[Any]):
        self.phases = phases
        self.validation_agent = GlobalValidationAgent()
        self.lineage_agent = LineageAgent()
        self.correction_logger = CorrectionLogger()
        self.monitoring_agent = MonitoringAgent()

    def run_pipeline(self, input_artifact: Any):
        result = input_artifact
        for idx, phase in enumerate(self.phases):
            result = phase.run(result)
            self.validation_agent.validate(result)
            self.lineage_agent.capture(result)
            self.monitoring_agent.track(result)
            self.correction_logger.track_decision({"phase_index": idx, "result": result})

            if idx == 4:
                rdl_result = phase.run(result)
                if isinstance(rdl_result, dict) and rdl_result.get("validation_status") != "passed":
                    self.correction_logger.log_issue(rdl_result)
                    self.self_heal(rdl_result)
        return result

    def self_heal(self, result: Dict):
        fix = self.correction_logger.auto_fix(result)
        return fix is not None
