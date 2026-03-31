"""
SemanticAgent: Agentic refactor for Phase 2 semantic reasoning
"""
from typing import Any, Dict, Optional
from .graph_builder import GraphBuilder
from .rule_engine import RuleEngine
from .llm_reasoner import LLMReasoner
from .confidence_evaluator import ConfidenceEvaluator
from .validation_hook import ValidationHook
from .lineage_hook import LineageHook

class SemanticAgent:
    """
    Agent responsible for building the semantic graph, resolving ambiguities, inferring business meaning, and supporting downstream generation.
    Handles hybrid reasoning, confidence scoring, validation, lineage, and self-healing.
    """
    def __init__(self, orchestrator=None, validation_agent=None, lineage_agent=None):
        self.orchestrator = orchestrator
        self.validation_hook = ValidationHook(validation_agent)
        self.lineage_hook = LineageHook(lineage_agent)
        self.graph_builder = GraphBuilder()
        self.rule_engine = RuleEngine()
        self.llm_reasoner = LLMReasoner()
        self.confidence_evaluator = ConfidenceEvaluator()

    def build_semantic_graph(self, metadata: Dict, parsed_structure: Dict, intent: Optional[Dict] = None) -> Dict:
        """
        Main entry point for semantic reasoning. Chooses strategy, validates, captures lineage, and handles errors.
        """
        semantic_log = []
        try:
            # 1. Fast path: rule-based graph building
            graph = self.graph_builder.build(metadata, parsed_structure)
            graph = self.rule_engine.apply_rules(graph, metadata, parsed_structure)
            semantic_log.append({"step": "rule_engine", "status": "applied"})
            # 2. If ambiguity or low confidence, use LLM path
            confidence = self.confidence_evaluator.evaluate(graph)
            if confidence < 0.9 or self._has_ambiguity(graph):
                graph = self.llm_reasoner.enrich(graph, metadata, parsed_structure, intent)
                semantic_log.append({"step": "llm_reasoner", "status": "used"})
                confidence = self.confidence_evaluator.evaluate(graph)
            # 3. Validation
            validation_results = self.validation_hook.validate(graph)
            graph["validation_results"] = validation_results
            # 4. Lineage
            lineage_events = self.lineage_hook.capture(graph)
            graph["lineage_events"] = lineage_events
            graph["confidence_score"] = confidence
            graph["semantic_log"] = semantic_log
            return graph
        except Exception as e:
            semantic_log.append({"step": "error", "message": str(e)})
            if self.orchestrator:
                recovery = self.orchestrator.handle_semantic_failure(metadata, parsed_structure, str(e), semantic_log)
                semantic_log.append({"step": "recovery", "message": recovery})
            return {"error": str(e), "semantic_log": semantic_log}

    def _has_ambiguity(self, graph: Dict) -> bool:
        # TODO: Implement ambiguity detection (naming conflicts, missing relationships, etc.)
        return False
