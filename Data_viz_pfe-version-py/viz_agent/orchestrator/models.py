"""
Modèles partagés pour l'orchestrateur
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime

class AgentType(Enum):
    DATA_EXTRACTION = "data_extraction"
    PARSING = "parsing"
    SEMANTIC_REASONING = "semantic_reasoning"
    SPECIFICATION = "specification"
    TRANSFORMATION = "transformation"
    EXPORT = "export"
    VALIDATION = "validation"
    LINEAGE = "lineage"

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

@dataclass
class ExecutionContext:
    execution_id: str
    intent: Dict[str, Any]
    context: Dict[str, Any]
    artifacts: Dict[str, Any]
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    lineage: List[Dict[str, Any]] = field(default_factory=list)
    def add_result(self, agent_type: AgentType, result: Any):
        self.intermediate_results[agent_type.value] = result
        self.lineage.append({"agent": agent_type.value, "timestamp": datetime.utcnow().isoformat(), "result_type": type(result).__name__})
    def get_result(self, agent_type: AgentType) -> Optional[Any]:
        return self.intermediate_results.get(agent_type.value)

@dataclass
class PipelineDefinition:
    pipeline_id: str
    steps: List[Dict[str, Any]]
    parallel_groups: List[List[str]]
    error_handling: Dict[str, Any]
    validation_points: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    execution_id: str
    status: ExecutionStatus
    pipeline: PipelineDefinition
    results: Dict[str, Any]
    errors: List[Dict[str, Any]]
    duration_ms: int
    retries: int
    validation_issues: List[Dict[str, Any]]
    final_artifact: Optional[Any] = None
