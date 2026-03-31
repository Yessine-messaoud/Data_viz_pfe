"""
TransformationAgent: Agentic refactor for Phase 4 transformation
"""
from typing import Any, Dict, Optional
from .data_model_transformer import DataModelTransformer
from .calculation_engine import CalculationEngine
from .visual_mapping_engine import VisualMappingEngine
from .optimization_engine import OptimizationEngine
from .compatibility_manager import CompatibilityManager
from .lineage_tracker import LineageTracker
from .validation_hook import ValidationHook

class TransformationAgent:
    """
    Agent responsible for converting abstract specifications into tool-specific models (Power BI, Tableau, etc.).
    Handles data model conversion, calculation translation, visual mapping, optimization, compatibility, validation, and lineage.
    """
    def __init__(self, orchestrator=None, validation_agent=None, lineage_agent=None, rules_config=None):
        self.orchestrator = orchestrator
        self.validation_hook = ValidationHook(validation_agent)
        self.lineage_tracker = LineageTracker(lineage_agent)
        self.data_model_transformer = DataModelTransformer(rules_config)
        self.calculation_engine = CalculationEngine(rules_config)
        self.visual_mapping_engine = VisualMappingEngine(rules_config)
        self.optimization_engine = OptimizationEngine(rules_config)
        self.compatibility_manager = CompatibilityManager(rules_config)

    def transform(self, abstract_spec: Dict, target_tool: str, context: Dict, intent: Optional[Dict] = None) -> Dict:
        """
        Main entry point for transformation. Handles conversion, optimization, validation, lineage, and error recovery.
        """
        transform_log = []
        try:
            # 1. Data model transformation
            tool_model = self.data_model_transformer.transform(abstract_spec, target_tool, context)
            transform_log.append({"step": "data_model", "status": "done"})
            # 2. Calculation translation
            tool_model = self.calculation_engine.transform(tool_model, target_tool, context)
            transform_log.append({"step": "calculation", "status": "done"})
            # 3. Visual mapping
            tool_model = self.visual_mapping_engine.transform(tool_model, target_tool, context)
            transform_log.append({"step": "visual_mapping", "status": "done"})
            # 4. Optimization
            tool_model = self.optimization_engine.optimize(tool_model, target_tool, context)
            transform_log.append({"step": "optimization", "status": "done"})
            # 5. Compatibility management
            tool_model, compatibility_log = self.compatibility_manager.resolve(tool_model, target_tool, context)
            transform_log.extend(compatibility_log)
            # 6. Validation
            validation_results = self.validation_hook.validate(tool_model)
            tool_model["validation_results"] = validation_results
            # 7. Lineage
            lineage_events = self.lineage_tracker.capture(tool_model)
            tool_model["lineage_events"] = lineage_events
            tool_model["transform_log"] = transform_log
            return tool_model
        except Exception as e:
            transform_log.append({"step": "error", "message": str(e)})
            if self.orchestrator:
                recovery = self.orchestrator.handle_transformation_failure(abstract_spec, target_tool, str(e), transform_log)
                transform_log.append({"step": "recovery", "message": recovery})
            return {"error": str(e), "transform_log": transform_log}
