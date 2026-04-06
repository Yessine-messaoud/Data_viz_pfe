"""
AgentFactory: Création et configuration des agents
"""
from typing import Dict, Any
from .models import AgentType
import logging

class AgentFactory:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("AgentFactory")
        self._agents_cache = {}
    def create(self, agent_type: AgentType) -> Any:
        if agent_type in self._agents_cache:
            return self._agents_cache[agent_type]
        agent_config = self.config.get(agent_type.value, {})
        # Import dynamique selon le type
        if agent_type == AgentType.DATA_EXTRACTION:
            from viz_agent.phase0_extraction.agent.data_extraction_agent import DataExtractionAgent
            agent = DataExtractionAgent(agent_config)
        elif agent_type == AgentType.PARSING:
            from viz_agent.phase1_parser.agent.parsing_agent import ParsingAgent
            agent = ParsingAgent(agent_config)
        elif agent_type == AgentType.SEMANTIC_REASONING:
            from viz_agent.phase2_semantic.agent.semantic_agent import SemanticAgent
            agent = SemanticAgent(agent_config)
        elif agent_type == AgentType.SPECIFICATION:
            from viz_agent.phase3_spec.specification_agent import SpecificationAgent
            agent = SpecificationAgent(agent_config)
        elif agent_type == AgentType.TRANSFORMATION:
            from viz_agent.phase4_transform.agent.transformation_agent import TransformationAgent
            agent = TransformationAgent(agent_config)
        elif agent_type == AgentType.EXPORT:
            from viz_agent.phase5_rdl.agent.export_agent import ExportAgent
            agent = ExportAgent(agent_config)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        self._agents_cache[agent_type] = agent
        return agent

    def get_agent(self, agent_name: str) -> Any:
        """Backward-compatible accessor used by legacy orchestrator code."""
        alias_map = {
            "data_extraction": AgentType.DATA_EXTRACTION,
            "parsing": AgentType.PARSING,
            "semantic_reasoning": AgentType.SEMANTIC_REASONING,
            "specification": AgentType.SPECIFICATION,
            "transformation": AgentType.TRANSFORMATION,
            "export": AgentType.EXPORT,
            # Legacy alias used in orchestrator.
            "phase5_rdl": AgentType.EXPORT,
        }
        if agent_name not in alias_map:
            raise ValueError(f"Unknown agent name: {agent_name}")
        return self.create(alias_map[agent_name])
