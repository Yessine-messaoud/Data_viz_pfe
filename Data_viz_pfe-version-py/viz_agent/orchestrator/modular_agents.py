from __future__ import annotations

from typing import Any

from viz_agent.orchestrator.base_agent import BaseAgent
from viz_agent.orchestrator.phase_agent import PhaseAgentResult
from viz_agent.orchestrator.phase_tool_agents import (
    Phase1ToolAgent,
    Phase2ToolAgent,
    Phase3ToolAgent,
    Phase4ToolAgent,
    Phase5ToolAgent,
)
from viz_agent.orchestrator.pipeline_context import PipelineContext
from viz_agent.orchestrator.runtime_validation import RDLRuntimeValidator
from viz_agent.orchestrator.validation_gates import ValidationGates


class ParsingAgent(BaseAgent):
    name = "parsing"

    def __init__(self, tool: Any | None = None) -> None:
        self._tool = tool or Phase1ToolAgent()

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        result = self._tool.execute(context.to_state_dict()).normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        if result.errors:
            context.add_error(self.name, "; ".join(result.errors))
        return result


class SemanticAgent(BaseAgent):
    name = "semantic_reasoning"

    def __init__(self, tool: Any | None = None) -> None:
        self._tool = tool or Phase2ToolAgent()

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        result = self._tool.execute(context.to_state_dict()).normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        if result.errors:
            context.add_error(self.name, "; ".join(result.errors))
        return result


class VisualizationAgent(BaseAgent):
    """Builds/updates abstract specification from semantic context."""

    name = "specification"

    def __init__(self, tool: Any | None = None) -> None:
        self._tool = tool or Phase3ToolAgent()

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        result = self._tool.execute(context.to_state_dict()).normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        if result.errors:
            context.add_error(self.name, "; ".join(result.errors))
        return result


class TransformationAgent(BaseAgent):
    """Transforms abstract specification into target tool model."""

    name = "transformation"

    def __init__(self, tool: Any | None = None) -> None:
        self._tool = tool or Phase4ToolAgent()

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        result = self._tool.execute(context.to_state_dict()).normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        if result.errors:
            context.add_error(self.name, "; ".join(result.errors))
        return result


class RDLAgent(BaseAgent):
    """Exports final RDL payload from transformed tool model."""

    name = "export"

    def __init__(self, tool: Any | None = None) -> None:
        self._tool = tool or Phase5ToolAgent()

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        result = self._tool.execute(context.to_state_dict()).normalized()
        context.update_from_phase_result(self.name, result.output, result.confidence)
        if result.errors:
            context.add_error(self.name, "; ".join(result.errors))
        return result


class RuntimeValidationAgent(BaseAgent):
    """Opens generated RDL and performs local runtime-compatible validation."""

    name = "runtime_validation"

    def __init__(self, validator: RDLRuntimeValidator | None = None) -> None:
        self._validator = validator or RDLRuntimeValidator(enable_schema_validation=True)

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        export_output = context.previous_outputs.get("export", {})
        export_payload = export_output.get("export_result", {}) if isinstance(export_output, dict) else {}
        rdl_path = ""
        if isinstance(export_payload, dict):
            rdl_path = str(export_payload.get("rdl_path") or "")
        if not rdl_path:
            rdl_path = str(context.artifacts.get("output_path") or "")

        if not rdl_path:
            result = self._result(
                status="error",
                confidence=0.0,
                output={
                    "runtime_validation": {
                        "status": "failure",
                        "errors": [
                            {
                                "type": "schema_error",
                                "message": "Missing output path for runtime validation",
                                "location": "output_path",
                                "severity": "P1",
                            }
                        ],
                        "confidence": 0.0,
                    }
                },
                errors=["Missing output path for runtime validation"],
                retry_hint="Ensure export phase writes a .rdl file and retry.",
            )
            context.update_from_phase_result(self.name, result.output, result.confidence)
            context.add_error(self.name, "; ".join(result.errors))
            return result

        runtime_result = self._validator.validate_file(rdl_path)
        success = str(runtime_result.get("status") or "failure").lower() == "success"
        confidence = float(runtime_result.get("confidence", 0.0) or 0.0)
        errors = [str(e.get("message") or "runtime validation failure") for e in (runtime_result.get("errors") or [])]

        result = self._result(
            status="success" if success else "error",
            confidence=confidence,
            output={"runtime_validation": runtime_result},
            errors=[] if success else errors,
            retry_hint="Apply runtime-aware fixes and retry." if not success else "",
        )
        context.update_from_phase_result(self.name, result.output, result.confidence)
        if result.errors:
            context.add_error(self.name, "; ".join(result.errors))
        return result


class ValidationAgent(BaseAgent):
    """Runs deterministic gates on already-produced phase outputs."""

    name = "validation"

    def __init__(self, gates: ValidationGates | None = None) -> None:
        self._gates = gates or ValidationGates()
        self._phases = ("parsing", "semantic_reasoning", "specification", "export", "runtime_validation")

    def execute(self, context: PipelineContext) -> PhaseAgentResult:
        issues: list[str] = []
        gate_results: dict[str, dict[str, Any]] = {}

        for phase_name in self._phases:
            output = context.previous_outputs.get(phase_name, {})
            if not isinstance(output, dict) or not output:
                continue
            gate = self._gates.validate(phase_name, output)
            gate_results[phase_name] = {"passed": gate.passed, "issues": list(gate.issues)}
            if not gate.passed:
                issues.extend(gate.issues)

        if issues:
            for issue in issues:
                context.add_error(self.name, issue)
            return self._result(
                status="error",
                confidence=0.2,
                output={"gate_results": gate_results},
                errors=issues,
                retry_hint="Fix invalid outputs for failing phase gates and retry.",
            )

        return self._result(status="success", confidence=1.0, output={"gate_results": gate_results})
