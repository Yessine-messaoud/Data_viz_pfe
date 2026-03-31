"""
PipelineBuilder: Construction dynamique de pipelines selon l'intention
"""
from typing import Dict, Any, List
from .models import PipelineDefinition
import logging
from datetime import datetime

class PipelineBuilder:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("PipelineBuilder")
        self.pipeline_templates = self._load_templates()

    def build(self, intent: Dict[str, Any], context: Dict[str, Any], artifacts: Dict[str, Any]) -> PipelineDefinition:
        intent_type = intent.get("type", "analysis")
        constraints = intent.get("constraints", {})
        self.logger.info(f"Building pipeline for intent: {intent_type}")
        template = self.pipeline_templates.get(intent_type, self._get_default_template())
        steps = self._adapt_steps(template["steps"], constraints, context, artifacts)
        parallel_groups = self._define_parallel_groups(steps, constraints)
        error_handling = self._configure_error_handling(constraints)
        validation_points = self._define_validation_points(steps, intent_type)
        return PipelineDefinition(
            pipeline_id=f"pipeline_{intent_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            steps=steps,
            parallel_groups=parallel_groups,
            error_handling=error_handling,
            validation_points=validation_points,
            metadata={"intent_type": intent_type, "constraints": constraints, "built_at": datetime.utcnow().isoformat()}
        )

    def _load_templates(self) -> Dict[str, Dict]:
        return {
            "conversion": {
                "steps": [
                    {"name": "data_extraction", "agent": "data_extraction", "required": True},
                    {"name": "parsing", "agent": "parsing", "required": True},
                    {"name": "semantic_analysis", "agent": "semantic_reasoning", "required": True},
                    {"name": "specification", "agent": "specification", "required": True},
                    {"name": "transformation", "agent": "transformation", "required": True},
                    {"name": "export", "agent": "export", "required": True}
                ],
                "parallel_groups": [],
                "error_handling": {"strategy": "retry", "max_retries": 3}
            },
            "generation": {
                "steps": [
                    {"name": "data_extraction", "agent": "data_extraction", "required": True},
                    {"name": "semantic_analysis", "agent": "semantic_reasoning", "required": True},
                    {"name": "specification", "agent": "specification", "required": True},
                    {"name": "export", "agent": "export", "required": True}
                ],
                "parallel_groups": [],
                "error_handling": {"strategy": "retry", "max_retries": 3}
            },
            "analysis": {
                "steps": [
                    {"name": "data_extraction", "agent": "data_extraction", "required": True},
                    {"name": "parsing", "agent": "parsing", "required": False},
                    {"name": "semantic_analysis", "agent": "semantic_reasoning", "required": True}
                ],
                "parallel_groups": [],
                "error_handling": {"strategy": "skip", "max_retries": 1}
            },
            "optimization": {
                "steps": [
                    {"name": "data_extraction", "agent": "data_extraction", "required": True},
                    {"name": "parsing", "agent": "parsing", "required": True},
                    {"name": "semantic_analysis", "agent": "semantic_reasoning", "required": True},
                    {"name": "specification", "agent": "specification", "required": True},
                    {"name": "export", "agent": "export", "required": True}
                ],
                "parallel_groups": [],
                "error_handling": {"strategy": "retry", "max_retries": 2}
            }
        }

    def _adapt_steps(self, base_steps: List[Dict], constraints: Dict, context: Dict, artifacts: Dict) -> List[Dict]:
        steps = base_steps.copy()
        if constraints.get("simplification"):
            steps.insert(3, {"name": "simplification", "agent": "transformation", "required": False, "inputs": {"mode": "simplify"}})
        if constraints.get("performance_focused"):
            steps.append({"name": "performance_optimization", "agent": "transformation", "required": False, "inputs": {"optimization": "performance"}})
        if constraints.get("mobile_target"):
            for step in steps:
                if step["name"] == "export":
                    step["inputs"] = step.get("inputs", {})
                    step["inputs"]["target_device"] = "mobile"
        for step in steps:
            step.setdefault("inputs", {})
            step["inputs"]["artifacts"] = artifacts
            step["inputs"]["context"] = context
        return steps

    def _define_parallel_groups(self, steps: List[Dict], constraints: Dict) -> List[List[str]]:
        parallel_groups = []
        independent_steps = [s["name"] for s in steps if not s.get("depends_on")]
        if len(independent_steps) > 1:
            if "data_extraction" in independent_steps and "parsing" in independent_steps:
                parallel_groups.append(["data_extraction", "parsing"])
        return parallel_groups

    def _configure_error_handling(self, constraints: Dict) -> Dict:
        error_handling = {"strategy": "retry", "max_retries": constraints.get("max_retries", 3), "backoff_factor": 2, "fallback_enabled": constraints.get("allow_fallback", True)}
        if constraints.get("strict_mode"):
            error_handling["strategy"] = "abort"
            error_handling["fallback_enabled"] = False
        return error_handling

    def _define_validation_points(self, steps: List[Dict], intent_type: str) -> List[str]:
        validation_points = []
        for step in steps:
            if step.get("name") in ["semantic_analysis", "specification", "export"]:
                validation_points.append(step["name"])
        return validation_points

    def _get_default_template(self) -> Dict:
        return {"steps": [{"name": "data_extraction", "agent": "data_extraction", "required": True}, {"name": "semantic_analysis", "agent": "semantic_reasoning", "required": True}], "parallel_groups": [], "error_handling": {"strategy": "retry", "max_retries": 2}}
