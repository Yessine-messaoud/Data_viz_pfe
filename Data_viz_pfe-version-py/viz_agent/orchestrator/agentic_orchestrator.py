# Fusion de la logique avancée d'orchestration (orchestrator_agent.py) avec l'observabilité agentique (agentic_orchestrator.py)
import logging
import asyncio
from datetime import datetime
import uuid
from .pipeline_builder import PipelineBuilder
from .error_handler import ErrorHandler
from .agent_factory import AgentFactory
from .pipeline_validator import PipelineValidator
from .models import AgentType, ExecutionStatus, ExecutionContext, PipelineDefinition, ExecutionResult

class OrchestratorAgent:
    """
    Agent orchestrateur principal
    Coordonne l'exécution des pipelines adaptatifs avec observabilité complète
    """
    def __init__(self, config: Dict[str, Any], phases: List[Any] = None):
        self.config = config
        self.logger = logging.getLogger("OrchestratorAgent")
        self.pipeline_builder = PipelineBuilder(config.get("pipeline", {}))
        self.agent_factory = AgentFactory(config.get("agents", {}))
        self.error_handler = ErrorHandler(config.get("error_handling", {}))
        self.validator = PipelineValidator(config.get("validation", {}))
        self.execution_history: List[ExecutionResult] = []
        self.agents: Dict[AgentType, Any] = {}
        self.metrics = {"executions": 0, "successful": 0, "failed": 0, "retries": 0, "avg_duration_ms": 0}
        # Observabilité agentique
        self.validation_agent = GlobalValidationAgent()
        self.lineage_agent = LineageAgent()
        self.correction_logger = CorrectionLogger()
        self.monitoring_agent = MonitoringAgent()
        self.phases = phases or []

    async def orchestrate(self, intent: Dict[str, Any], context: Dict[str, Any], artifacts: Dict[str, Any]) -> ExecutionResult:
        execution_id = self._generate_execution_id()
        self.metrics["executions"] += 1
        start_time = datetime.utcnow()
        try:
            self.logger.info(f"Starting orchestration {execution_id} - Intent: {intent.get('type')}")
            exec_context = ExecutionContext(
                execution_id=execution_id,
                intent=intent,
                context=context,
                artifacts=artifacts
            )
            pipeline = self.pipeline_builder.build(intent, context, artifacts)
            self.logger.info(f"Pipeline built: {len(pipeline.steps)} steps")
            validation = self.validator.validate_pipeline(pipeline, exec_context)
            if not validation.is_valid:
                self.logger.warning(f"Pipeline validation issues: {validation.issues}")
                pipeline = self._auto_correct_pipeline(pipeline, validation)
            # Observabilité: validation globale, lineage, monitoring, correction
            self.validation_agent.validate(pipeline, exec_context)
            self.lineage_agent.capture(pipeline)
            self.monitoring_agent.track(pipeline)
            # Exécution pipeline
            result = await self._execute_pipeline(pipeline, exec_context)
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result.duration_ms = duration
            self._update_metrics(result)
            self.execution_history.append(result)
            return result
        except Exception as e:
            self.logger.error(f"Orchestration failed: {e}")
            self.metrics["failed"] += 1
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                pipeline=PipelineDefinition(pipeline_id="error", steps=[], parallel_groups=[], error_handling={}, validation_points=[]),
                results={},
                errors=[{"error": str(e)}],
                duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                retries=0,
                validation_issues=[]
            )

    async def _execute_pipeline(self, pipeline: PipelineDefinition, context: ExecutionContext) -> ExecutionResult:
        results = {}
        errors = []
        validation_issues = []
        retries = 0
        max_retries = self.config.get("max_retries", 3)
        completed_steps = set()
        failed_steps = set()
        while retries <= max_retries:
            try:
                for step in pipeline.steps:
                    step_name = step.get("name")
                    # Observabilité à chaque étape
                    self.validation_agent.validate(step, context)
                    self.lineage_agent.capture(step)
                    self.monitoring_agent.track(step)
                    self.correction_logger.track_decision(step)
                    # Exécution réelle de l'agent/phase
                    # ... (logique spécifique à chaque agent)
                    # Toujours exécuter la phase 5 (validation)
                    if step_name == "phase5_rdl":
                        rdl_result = self.agent_factory.get_agent("phase5_rdl").run(step)
                        if rdl_result.get('validation_status') != 'passed':
                            self.correction_logger.log_issue(rdl_result)
                            self.self_heal(rdl_result)
                break
            except Exception as e:
                errors.append(str(e))
                retries += 1
        return ExecutionResult(
            execution_id=context.execution_id,
            status=ExecutionStatus.SUCCESS if not errors else ExecutionStatus.FAILED,
            pipeline=pipeline,
            results=results,
            errors=errors,
            duration_ms=0,
            retries=retries,
            validation_issues=validation_issues
        )

    def _generate_execution_id(self) -> str:
        return str(uuid.uuid4())

    def _auto_correct_pipeline(self, pipeline, validation):
        # Stub: auto-correction logic
        return pipeline

    def _update_metrics(self, result):
        # Stub: update metrics
        pass

    def self_heal(self, result: Dict):
        if result.get('error_type') == 'validation':
            fix = self.correction_logger.auto_fix(result)
            if fix:
                # Re-run phase 5 after fix
                return self.agent_factory.get_agent("phase5_rdl").run(result)
        # Escalate or abort if not recoverable
        return None
from typing import Any, Dict, List
import datetime

class GlobalValidationAgent:
    def validate(self, *artifacts) -> Dict:
        # Cross-phase validation logic (stub)
        return {"global_score": 1.0, "issues": []}

class LineageAgent:
    def __init__(self):
        self.entries = []
    def capture(self, artifact: Dict):
        self.entries.append({"timestamp": datetime.datetime.utcnow().isoformat(), "artifact": artifact})

class CorrectionLogger:
    def __init__(self):
        self.corrections = []
        self.decisions = []
    def log_issue(self, issue: Dict):
        self.corrections.append(issue)
    def auto_fix(self, result: Dict) -> bool:
        # Stub: always returns False (no fix)
        return False
    def track_decision(self, result: Dict):
        self.decisions.append(result)

class MonitoringAgent:
    def __init__(self):
        self.metrics = []
    def track(self, artifact: Dict):
        self.metrics.append({"timestamp": datetime.datetime.utcnow().isoformat(), "artifact": artifact})

class Orchestrator:
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
            self.correction_logger.track_decision(result)
            # Always run Phase 5 (validation)
            if idx == 4:  # Phase 5
                rdl_result = phase.run(result)
                if rdl_result.get('validation_status') != 'passed':
                    self.correction_logger.log_issue(rdl_result)
                    self.self_heal(rdl_result)
        return result
    def self_heal(self, result: Dict):
        if result.get('error_type') == 'validation':
            fix = self.correction_logger.auto_fix(result)
            if fix:
                # Re-run phase 5 after fix
                return self.phases[4].run(result)
        # Escalate or abort if not recoverable
        return None
