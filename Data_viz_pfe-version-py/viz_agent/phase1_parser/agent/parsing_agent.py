"""
ParsingAgent: Agentic refactor for Phase 1 BI parsing
"""
from typing import Any, Dict, Optional
from .deterministic_parser import DeterministicParser
from .heuristic_parser import HeuristicParser
from .llm_parser import LLMParser
from .validation_hook import ValidationHook
from .lineage_hook import LineageHook

class ParsingAgent:
    """
    Agent responsible for extracting dashboard structure, visuals, filters, bindings, and layout from BI artifacts.
    Handles deterministic, heuristic, and LLM-assisted parsing, validation, lineage, and self-healing.
    """
    def __init__(self, orchestrator=None, validation_agent=None, lineage_agent=None):
        self.orchestrator = orchestrator
        self.validation_hook = ValidationHook(validation_agent)
        self.lineage_hook = LineageHook(lineage_agent)
        self.deterministic_parser = DeterministicParser()
        self.heuristic_parser = HeuristicParser()
        self.llm_parser = LLMParser()

    def parse(self, artifact_path: str, metadata: Dict, context: Dict) -> Dict:
        """
        Main entry point for parsing. Chooses strategy, validates, captures lineage, and handles errors.
        """
        parsing_log = []
        try:
            # 1. Deterministic parsing
            result = self.deterministic_parser.parse(artifact_path, metadata)
            parsing_log.append({"step": "deterministic", "status": "success"})
            # 2. Heuristic fallback if needed
            if not self._is_complete(result):
                result = self.heuristic_parser.parse(artifact_path, metadata, result)
                parsing_log.append({"step": "heuristic", "status": "used"})
            # 3. LLM-assisted fallback if still incomplete
            if not self._is_complete(result):
                result = self.llm_parser.parse(artifact_path, metadata, result)
                parsing_log.append({"step": "llm", "status": "used"})
            # 4. Validation
            validation_results = self.validation_hook.validate(result)
            result["validation_results"] = validation_results
            # 5. Lineage
            lineage_events = self.lineage_hook.capture(result)
            result["lineage_events"] = lineage_events
            result["parsing_log"] = parsing_log
            return result
        except Exception as e:
            parsing_log.append({"step": "error", "message": str(e)})
            if self.orchestrator:
                recovery = self.orchestrator.handle_parsing_failure(artifact_path, str(e), parsing_log)
                parsing_log.append({"step": "recovery", "message": recovery})
            return {"error": str(e), "parsing_log": parsing_log}

    def _is_complete(self, result: Dict) -> bool:
        if not isinstance(result, dict):
            return False
        dashboards = result.get("dashboards")
        visuals = result.get("visuals")
        return isinstance(dashboards, list) and len(dashboards) > 0 and isinstance(visuals, list)
