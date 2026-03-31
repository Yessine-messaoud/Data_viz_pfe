"""
Specification Agent principal module
Orchestration de la génération de la spécification abstraite BI
"""
from typing import Any, Dict
from .components.model_mapper import ModelMapper
from .components.logic_encoder import LogicEncoder
from .components.visualization_planner import VisualizationPlanner
from .components.layout_planner import LayoutPlanner
from .components.spec_validator import SpecValidator
from .components.confidence_scorer import ConfidenceScorer
from .components.rules_config import RulesConfig
from .components.exporter import Exporter
from .components.semantic_cache import SemanticCache

class SpecificationAgent:
    """
    Orchestrates the transformation of a semantic graph and intent into an abstract BI specification.
    """
    def __init__(self, rules_path: str = None):
        self.rules = RulesConfig(rules_path)
        self.model_mapper = ModelMapper(self.rules)
        self.logic_encoder = LogicEncoder(self.rules)
        self.visualization_planner = VisualizationPlanner(self.rules)
        self.layout_planner = LayoutPlanner(self.rules)
        self.spec_validator = SpecValidator(self.rules)
        self.confidence_scorer = ConfidenceScorer(self.rules)
        self.exporter = Exporter()
        self.cache = SemanticCache()

    def generate_specification(self, semantic_graph: Any, intent: Dict, context: Dict) -> Dict:
        """
        Main entry point: generates the abstract specification from semantic graph, intent, and context.
        """
        # 1. Model mapping
        data_model = self.model_mapper.map(semantic_graph)
        # 2. Logic encoding
        business_logic = self.logic_encoder.encode(semantic_graph, intent)
        # 3. Visualization planning
        viz_model = self.visualization_planner.plan(data_model, business_logic, intent, context)
        # 4. Layout planning
        presentation = self.layout_planner.plan(viz_model, context)
        # 5. Validation
        self.spec_validator.validate(data_model, business_logic, viz_model, presentation)
        # 6. Confidence scoring
        confidence = self.confidence_scorer.score(data_model, business_logic, viz_model, presentation)
        # 7. Build final spec
        spec = {
            "abstract_data_model": data_model,
            "visualization_model": viz_model,
            "business_logic_model": business_logic,
            "presentation_model": presentation,
            "metadata": self._build_metadata(intent),
            "confidence_score": confidence,
        }
        # 8. Caching
        self.cache.store(semantic_graph, spec)
        return spec

    def export(self, spec: Dict, format: str = "json") -> str:
        """
        Export the specification in the requested format (json, yaml, markdown, graphql).
        """
        return self.exporter.export(spec, format)

    def _build_metadata(self, intent: Dict) -> Dict:
        # Build metadata block (id, timestamp, intent, etc.)
        import uuid, datetime
        return {
            "spec_id": str(uuid.uuid4()),
            "created_at": datetime.datetime.now().isoformat(),
            "source_intent": intent,
        }
