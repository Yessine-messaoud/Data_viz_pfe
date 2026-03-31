"""
PipelineValidator: Validation des pipelines avant exécution
"""
from typing import Any, List
from .models import PipelineDefinition, ExecutionContext

class PipelineValidator:
    def __init__(self, config: dict):
        self.config = config
    def validate_pipeline(self, pipeline: PipelineDefinition, context: ExecutionContext) -> Any:
        issues = []
        for step in pipeline.steps:
            agent_type = step.get("agent")
            if not agent_type:
                issues.append(f"Step {step.get('name')} has no agent specified")
        if self._has_circular_dependency(pipeline):
            issues.append("Circular dependency detected in pipeline")
        for step in pipeline.steps:
            inputs = step.get("inputs", {})
            required_inputs = step.get("required_inputs", [])
            for req in required_inputs:
                if req not in inputs and req not in ["artifacts", "context"]:
                    issues.append(f"Missing required input '{req}' for step {step.get('name')}")
        return type('ValidationResult', (), {"is_valid": len(issues) == 0, "issues": issues, "critical": len(issues) > 0})()
    def _has_circular_dependency(self, pipeline: PipelineDefinition) -> bool:
        graph = {}
        for step in pipeline.steps:
            step_name = step.get("name")
            depends_on = step.get("depends_on", [])
            graph[step_name] = depends_on
        visited = set()
        rec_stack = set()
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False
        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False
