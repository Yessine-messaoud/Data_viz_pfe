# Prompt pour le développement de l'Orchestrator Agent avec GPT-4.1

## Prompt Principal

```
Je souhaite développer un **Orchestrator Agent** dans le cadre d'une architecture agentique pour la transformation et génération de visualisations BI. Cet agent est le cœur décisionnel du système, responsable de la coordination dynamique de tous les autres agents, de la construction du pipeline d'exécution adaptatif, et de la gestion des erreurs avec des mécanismes de self-healing.

## Contexte technique

### Architecture générale
Le système est structuré en trois couches :
- **Interaction Layer** : Conversation Agent
- **Cognition Layer** : Intent Detection Agent, **Orchestrator Agent**
- **Execution Layer** : Data Extraction, Parsing, Semantic Reasoning, Specification, Transformation, Export Agents

### Position de l'Orchestrator dans l'architecture

```
Conversation Agent → Intent Detection Agent → Orchestrator Agent → [Execution Agents] → Export
                                                    ↑
                                            Self-Healing Loop
                                                    ↓
                                              Validation Agent
```

L'Orchestrator Agent reçoit :
1. **Intent Object** : intention formalisée par l'Intent Detection Agent
2. **Context & Preferences** : contexte utilisateur et préférences
3. **Artifacts Metadata** : métadonnées sur les artefacts fournis
4. **Validation Feedback** : retours du Validation Agent pour les corrections

### Objectifs de l'Orchestrator Agent

1. **Construction dynamique du pipeline** : sélectionner et ordonner les agents nécessaires
2. **Gestion adaptative** : activer/désactiver des modules selon l'intention
3. **Orchestration des flux** : coordonner l'exécution séquentielle et parallèle
4. **Gestion des erreurs** : détecter, isoler et corriger les échecs
5. **Self-healing** : déclencher des boucles de correction ciblées
6. **Traçabilité** : maintenir l'état d'exécution et le lineage opérationnel

## Partie 1 : Structure de l'Orchestrator

### 1.1 Interface principale

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
import logging
import asyncio
from datetime import datetime
import uuid

class AgentType(Enum):
    """Types d'agents disponibles dans le système"""
    DATA_EXTRACTION = "data_extraction"
    PARSING = "parsing"
    SEMANTIC_REASONING = "semantic_reasoning"
    SPECIFICATION = "specification"
    TRANSFORMATION = "transformation"
    EXPORT = "export"
    VALIDATION = "validation"
    LINEAGE = "lineage"

class ExecutionStatus(Enum):
    """Statuts d'exécution d'un pipeline"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

@dataclass
class ExecutionContext:
    """Contexte d'exécution partagé entre les agents"""
    execution_id: str
    intent: Dict[str, Any]
    context: Dict[str, Any]
    artifacts: Dict[str, Any]
    intermediate_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    lineage: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_result(self, agent_type: AgentType, result: Any):
        """Ajoute un résultat intermédiaire"""
        self.intermediate_results[agent_type.value] = result
        self.lineage.append({
            "agent": agent_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "result_type": type(result).__name__
        })
    
    def get_result(self, agent_type: AgentType) -> Optional[Any]:
        """Récupère un résultat intermédiaire"""
        return self.intermediate_results.get(agent_type.value)

@dataclass
class PipelineDefinition:
    """Définition d'un pipeline d'exécution"""
    pipeline_id: str
    steps: List[Dict[str, Any]]
    parallel_groups: List[List[str]]
    error_handling: Dict[str, Any]
    validation_points: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    """Résultat d'exécution du pipeline"""
    execution_id: str
    status: ExecutionStatus
    pipeline: PipelineDefinition
    results: Dict[str, Any]
    errors: List[Dict[str, Any]]
    duration_ms: int
    retries: int
    validation_issues: List[Dict[str, Any]]
    final_artifact: Optional[Any] = None
```

### 1.2 Orchestrator Agent Principal

```python
class OrchestratorAgent:
    """
    Agent orchestrateur principal
    Coordonne l'exécution des pipelines adaptatifs
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("OrchestratorAgent")
        self.pipeline_builder = PipelineBuilder(config.get("pipeline", {}))
        self.agent_factory = AgentFactory(config.get("agents", {}))
        self.error_handler = ErrorHandler(config.get("error_handling", {}))
        self.validator = PipelineValidator(config.get("validation", {}))
        self.execution_history: List[ExecutionResult] = []
        
        # Agents disponibles
        self.agents: Dict[AgentType, Any] = {}
        
        # Métriques
        self.metrics = {
            "executions": 0,
            "successful": 0,
            "failed": 0,
            "retries": 0,
            "avg_duration_ms": 0
        }
    
    async def orchestrate(self, 
                          intent: Dict[str, Any],
                          context: Dict[str, Any],
                          artifacts: Dict[str, Any]) -> ExecutionResult:
        """
        Point d'entrée principal de l'orchestration
        
        Args:
            intent: Intention détectée (type, contraintes, plan)
            context: Contexte utilisateur et préférences
            artifacts: Artefacts fournis par l'utilisateur
        
        Returns:
            ExecutionResult avec l'artefact final
        """
        execution_id = self._generate_execution_id()
        self.metrics["executions"] += 1
        
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Starting orchestration {execution_id} - Intent: {intent.get('type')}")
            
            # 1. Créer le contexte d'exécution
            exec_context = ExecutionContext(
                execution_id=execution_id,
                intent=intent,
                context=context,
                artifacts=artifacts
            )
            
            # 2. Construire le pipeline dynamique
            pipeline = self.pipeline_builder.build(intent, context, artifacts)
            self.logger.info(f"Pipeline built: {len(pipeline.steps)} steps")
            
            # 3. Valider le pipeline
            validation = self.validator.validate_pipeline(pipeline, exec_context)
            if not validation.is_valid:
                self.logger.warning(f"Pipeline validation issues: {validation.issues}")
                # Tentative d'auto-correction
                pipeline = self._auto_correct_pipeline(pipeline, validation)
            
            # 4. Exécuter le pipeline avec gestion d'erreurs
            result = await self._execute_pipeline(pipeline, exec_context)
            
            # 5. Calculer la durée
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result.duration_ms = duration
            
            # 6. Mettre à jour les métriques
            self._update_metrics(result)
            
            # 7. Enregistrer dans l'historique
            self.execution_history.append(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Orchestration failed: {e}")
            self.metrics["failed"] += 1
            
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                pipeline=PipelineDefinition(pipeline_id="error", steps=[]),
                results={},
                errors=[{"error": str(e), "traceback": self._get_traceback(e)}],
                duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                retries=0,
                validation_issues=[]
            )
    
    async def _execute_pipeline(self, 
                                 pipeline: PipelineDefinition, 
                                 context: ExecutionContext) -> ExecutionResult:
        """
        Exécute le pipeline avec gestion parallèle et séquentielle
        """
        results = {}
        errors = []
        validation_issues = []
        retries = 0
        max_retries = self.config.get("max_retries", 3)
        
        # État d'avancement
        completed_steps = set()
        failed_steps = set()
        
        while retries <= max_retries:
            try:
                # Exécuter les étapes séquentielles
                for step in pipeline.steps:
                    step_name = step.get("name")
                    agent_type = step.get("agent")
                    
                    if step_name in completed_steps:
                        continue
                    
                    if step_name in failed_steps and retries == 0:
                        continue
                    
                    self.logger.info(f"Executing step: {step_name} (retry {retries})")
                    
                    try:
                        # Récupérer l'agent
                        agent = await self._get_agent(agent_type)
                        
                        # Préparer les inputs
                        inputs = self._prepare_inputs(step, context, results)
                        
                        # Exécuter avec timeout
                        result = await self._execute_with_timeout(
                            agent, inputs, step.get("timeout", 300)
                        )
                        
                        # Valider le résultat
                        validation = await self._validate_step_result(step, result, context)
                        if not validation.is_valid:
                            validation_issues.extend(validation.issues)
                            if validation.critical:
                                raise ValidationError(f"Critical validation failed: {validation.issues}")
                        
                        # Stocker le résultat
                        results[step_name] = result
                        context.add_result(agent_type, result)
                        completed_steps.add(step_name)
                        
                    except Exception as e:
                        self.logger.error(f"Step {step_name} failed: {e}")
                        failed_steps.add(step_name)
                        errors.append({
                            "step": step_name,
                            "error": str(e),
                            "retry": retries
                        })
                        
                        # Gérer l'erreur
                        recovery_action = self.error_handler.handle_error(
                            e, step, context, retries
                        )
                        
                        if recovery_action == RecoveryAction.RETRY:
                            continue
                        elif recovery_action == RecoveryAction.FALLBACK:
                            fallback_result = await self._execute_fallback(step, context)
                            results[step_name] = fallback_result
                            completed_steps.add(step_name)
                        elif recovery_action == RecoveryAction.SKIP:
                            self.logger.warning(f"Skipping step {step_name}")
                            results[step_name] = None
                            completed_steps.add(step_name)
                        elif recovery_action == RecoveryAction.ABORT:
                            raise
                
                # Exécuter les groupes parallèles
                for group in pipeline.parallel_groups:
                    if all(g in completed_steps for g in group):
                        continue
                    
                    self.logger.info(f"Executing parallel group: {group}")
                    group_results = await self._execute_parallel(group, context, results)
                    results.update(group_results)
                    completed_steps.update(group)
                
                # Vérifier que toutes les étapes sont complétées
                if len(completed_steps) == len(pipeline.steps) + len(pipeline.parallel_groups):
                    break
                
            except Exception as e:
                if retries >= max_retries:
                    raise
                
                retries += 1
                self.metrics["retries"] += 1
                self.logger.warning(f"Pipeline failed, retrying ({retries}/{max_retries}): {e}")
                
                # Nettoyer l'état pour retry
                completed_steps = set()
                failed_steps = set()
                results = {}
                await asyncio.sleep(2 ** retries)  # Exponential backoff
        
        # Construire le résultat final
        final_artifact = results.get("export", {}).get("artifact")
        
        return ExecutionResult(
            execution_id=context.execution_id,
            status=ExecutionStatus.COMPLETED if not errors else ExecutionStatus.PARTIAL,
            pipeline=pipeline,
            results=results,
            errors=errors,
            duration_ms=0,
            retries=retries,
            validation_issues=validation_issues,
            final_artifact=final_artifact
        )
    
    async def _execute_parallel(self, 
                                 step_names: List[str], 
                                 context: ExecutionContext,
                                 previous_results: Dict) -> Dict[str, Any]:
        """Exécute plusieurs étapes en parallèle"""
        tasks = []
        
        for step_name in step_names:
            step = self._find_step_by_name(step_name, context.pipeline.steps)
            if step:
                agent_type = step.get("agent")
                inputs = self._prepare_inputs(step, context, previous_results)
                agent = await self._get_agent(agent_type)
                
                tasks.append(self._execute_with_timeout(agent, inputs, step.get("timeout", 300)))
            else:
                tasks.append(asyncio.sleep(0, result=None))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Mapper les résultats
        output = {}
        for step_name, result in zip(step_names, results):
            if isinstance(result, Exception):
                self.logger.error(f"Parallel step {step_name} failed: {result}")
                output[step_name] = None
            else:
                output[step_name] = result
        
        return output
    
    async def _get_agent(self, agent_type: Union[AgentType, str]) -> Any:
        """Récupère ou instancie un agent"""
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)
        
        if agent_type not in self.agents:
            self.agents[agent_type] = self.agent_factory.create(agent_type)
        
        return self.agents[agent_type]
    
    def _prepare_inputs(self, step: Dict, context: ExecutionContext, previous_results: Dict) -> Dict:
        """Prépare les inputs pour un agent"""
        inputs = {}
        
        # Inputs explicites
        for input_name, input_source in step.get("inputs", {}).items():
            if input_source.startswith("$context."):
                key = input_source.replace("$context.", "")
                inputs[input_name] = self._get_nested_value(context.__dict__, key)
            elif input_source.startswith("$result."):
                step_name = input_source.split(".")[1]
                field = ".".join(input_source.split(".")[2:])
                result = previous_results.get(step_name)
                if result and field:
                    inputs[input_name] = self._get_nested_value(result, field)
                else:
                    inputs[input_name] = result
            else:
                inputs[input_name] = input_source
        
        # Inputs par défaut
        inputs.setdefault("context", context.context)
        inputs.setdefault("intent", context.intent)
        
        return inputs
    
    async def _execute_with_timeout(self, agent: Any, inputs: Dict, timeout_seconds: int) -> Any:
        """Exécute un agent avec timeout"""
        try:
            return await asyncio.wait_for(
                self._call_agent(agent, inputs),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Agent execution timed out after {timeout_seconds}s")
    
    async def _call_agent(self, agent: Any, inputs: Dict) -> Any:
        """Appelle l'agent avec la méthode appropriée"""
        # Différents agents ont des interfaces différentes
        if hasattr(agent, "execute"):
            return await agent.execute(**inputs)
        elif hasattr(agent, "process"):
            return await agent.process(**inputs)
        elif callable(agent):
            return await agent(**inputs)
        else:
            raise ValueError(f"Agent {type(agent)} has no callable interface")
    
    def _generate_execution_id(self) -> str:
        """Génère un ID d'exécution unique"""
        return f"exec_{uuid.uuid4().hex[:12]}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    def _update_metrics(self, result: ExecutionResult):
        """Met à jour les métriques"""
        if result.status == ExecutionStatus.COMPLETED:
            self.metrics["successful"] += 1
        
        total_duration = self.metrics["avg_duration_ms"] * (self.metrics["executions"] - 1)
        total_duration += result.duration_ms
        self.metrics["avg_duration_ms"] = total_duration / self.metrics["executions"]
```

## Partie 2 : Pipeline Builder - Construction Dynamique

```python
class PipelineBuilder:
    """
    Constructeur de pipelines dynamiques basé sur l'intention
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("PipelineBuilder")
        
        # Templates de pipelines par type d'intention
        self.pipeline_templates = self._load_templates()
    
    def build(self, 
              intent: Dict[str, Any], 
              context: Dict[str, Any],
              artifacts: Dict[str, Any]) -> PipelineDefinition:
        """
        Construit un pipeline adapté à l'intention
        
        Args:
            intent: Intention détectée (type, contraintes, plan)
            context: Contexte utilisateur
            artifacts: Artefacts fournis
        
        Returns:
            PipelineDefinition configuré
        """
        intent_type = intent.get("type", "analysis")
        constraints = intent.get("constraints", {})
        
        self.logger.info(f"Building pipeline for intent: {intent_type}")
        
        # 1. Sélectionner le template de base
        template = self.pipeline_templates.get(intent_type, self._get_default_template())
        
        # 2. Adapter selon les contraintes
        steps = self._adapt_steps(template["steps"], constraints, context, artifacts)
        
        # 3. Définir les groupes parallèles
        parallel_groups = self._define_parallel_groups(steps, constraints)
        
        # 4. Configurer la gestion d'erreurs
        error_handling = self._configure_error_handling(constraints)
        
        # 5. Définir les points de validation
        validation_points = self._define_validation_points(steps, intent_type)
        
        return PipelineDefinition(
            pipeline_id=f"pipeline_{intent_type}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            steps=steps,
            parallel_groups=parallel_groups,
            error_handling=error_handling,
            validation_points=validation_points,
            metadata={
                "intent_type": intent_type,
                "constraints": constraints,
                "built_at": datetime.utcnow().isoformat()
            }
        )
    
    def _load_templates(self) -> Dict[str, Dict]:
        """Charge les templates de pipelines"""
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
    
    def _adapt_steps(self, 
                     base_steps: List[Dict], 
                     constraints: Dict,
                     context: Dict,
                     artifacts: Dict) -> List[Dict]:
        """Adapte les étapes selon les contraintes"""
        steps = base_steps.copy()
        
        # Ajouter ou supprimer des étapes selon les contraintes
        if constraints.get("simplification"):
            # Ajouter une étape de simplification
            steps.insert(3, {
                "name": "simplification",
                "agent": "transformation",
                "required": False,
                "inputs": {"mode": "simplify"}
            })
        
        if constraints.get("performance_focused"):
            # Ajouter une étape d'optimisation
            steps.append({
                "name": "performance_optimization",
                "agent": "transformation",
                "required": False,
                "inputs": {"optimization": "performance"}
            })
        
        if constraints.get("mobile_target"):
            # Modifier l'étape d'export pour mobile
            for step in steps:
                if step["name"] == "export":
                    step["inputs"] = step.get("inputs", {})
                    step["inputs"]["target_device"] = "mobile"
        
        # Configurer les inputs des agents
        for step in steps:
            step.setdefault("inputs", {})
            step["inputs"]["artifacts"] = artifacts
            step["inputs"]["context"] = context
        
        return steps
    
    def _define_parallel_groups(self, steps: List[Dict], constraints: Dict) -> List[List[str]]:
        """Définit les groupes d'étapes pouvant s'exécuter en parallèle"""
        parallel_groups = []
        
        # Identifier les étapes indépendantes
        independent_steps = [s["name"] for s in steps if not s.get("depends_on")]
        
        # Grouper par type
        if len(independent_steps) > 1:
            # Extraction et parsing peuvent être parallèles
            if "data_extraction" in independent_steps and "parsing" in independent_steps:
                parallel_groups.append(["data_extraction", "parsing"])
        
        return parallel_groups
    
    def _configure_error_handling(self, constraints: Dict) -> Dict:
        """Configure la gestion d'erreurs selon les contraintes"""
        error_handling = {
            "strategy": "retry",
            "max_retries": constraints.get("max_retries", 3),
            "backoff_factor": 2,
            "fallback_enabled": constraints.get("allow_fallback", True)
        }
        
        if constraints.get("strict_mode"):
            error_handling["strategy"] = "abort"
            error_handling["fallback_enabled"] = False
        
        return error_handling
    
    def _define_validation_points(self, steps: List[Dict], intent_type: str) -> List[str]:
        """Définit les points où la validation est obligatoire"""
        validation_points = []
        
        # Points de validation critiques
        for step in steps:
            if step.get("name") in ["semantic_analysis", "specification", "export"]:
                validation_points.append(step["name"])
        
        return validation_points
    
    def _get_default_template(self) -> Dict:
        """Retourne le template par défaut"""
        return {
            "steps": [
                {"name": "data_extraction", "agent": "data_extraction", "required": True},
                {"name": "semantic_analysis", "agent": "semantic_reasoning", "required": True}
            ],
            "parallel_groups": [],
            "error_handling": {"strategy": "retry", "max_retries": 2}
        }
```

## Partie 3 : Gestion des Erreurs et Self-Healing

```python
from enum import Enum
from typing import Dict, Any, Optional
import traceback

class RecoveryAction(Enum):
    """Actions de récupération possibles"""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"
    RECONFIGURE = "reconfigure"

class ErrorHandler:
    """Gestionnaire d'erreurs avec stratégies de self-healing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("ErrorHandler")
        self.fallback_registry = FallbackRegistry()
        self.recovery_strategies = self._load_strategies()
    
    def handle_error(self, 
                     error: Exception, 
                     step: Dict[str, Any], 
                     context: ExecutionContext,
                     retry_count: int) -> RecoveryAction:
        """
        Détermine l'action de récupération appropriée
        
        Args:
            error: L'erreur survenue
            step: L'étape qui a échoué
            context: Contexte d'exécution
            retry_count: Nombre de retries déjà effectués
        
        Returns:
            RecoveryAction à exécuter
        """
        error_type = type(error).__name__
        step_name = step.get("name")
        
        self.logger.warning(f"Handling error in {step_name}: {error_type} - {error}")
        
        # 1. Vérifier si on peut retry
        max_retries = step.get("max_retries", self.config.get("max_retries", 3))
        if retry_count < max_retries and self._is_retryable(error):
            self.logger.info(f"Retrying step {step_name} ({retry_count + 1}/{max_retries})")
            return RecoveryAction.RETRY
        
        # 2. Vérifier si un fallback existe
        if step.get("fallback_enabled", True):
            fallback = self.fallback_registry.get_fallback(step_name, error_type)
            if fallback:
                self.logger.info(f"Using fallback for {step_name}: {fallback['name']}")
                return RecoveryAction.FALLBACK
        
        # 3. Vérifier si l'étape peut être ignorée
        if not step.get("required", True):
            self.logger.warning(f"Skipping non-required step {step_name}")
            return RecoveryAction.SKIP
        
        # 4. Abort si aucune récupération possible
        self.logger.error(f"No recovery possible for {step_name}, aborting")
        return RecoveryAction.ABORT
    
    def _is_retryable(self, error: Exception) -> bool:
        """Détermine si l'erreur peut être retryée"""
        retryable_errors = [
            "TimeoutError",
            "ConnectionError",
            "NetworkError",
            "TransientError",
            "RateLimitError"
        ]
        
        error_type = type(error).__name__
        
        # Erreurs temporaires sont retryables
        if error_type in retryable_errors:
            return True
        
        # Erreurs de validation nécessitent reconfiguration
        if "ValidationError" in error_type:
            return False
        
        # Erreurs de données peuvent être retryées après nettoyage
        if "DataError" in error_type:
            return True
        
        return False
    
    def _load_strategies(self) -> Dict:
        """Charge les stratégies de récupération"""
        return {
            "parsing_error": {
                "action": "fallback",
                "fallback": "llm_parsing"
            },
            "semantic_error": {
                "action": "retry",
                "max_retries": 2
            },
            "transformation_error": {
                "action": "reconfigure",
                "alternative_strategy": "simplify"
            }
        }

class FallbackRegistry:
    """Registre des stratégies de fallback par agent"""
    
    def __init__(self):
        self.fallbacks = self._init_fallbacks()
    
    def _init_fallbacks(self) -> Dict[str, Dict[str, Dict]]:
        """Initialise les fallbacks disponibles"""
        return {
            "parsing": {
                "ParseError": {
                    "name": "llm_assisted_parsing",
                    "handler": "LLMParser",
                    "description": "Use LLM to parse complex structures"
                },
                "SchemaError": {
                    "name": "schema_inference",
                    "handler": "SchemaInferrer",
                    "description": "Infer schema from data"
                }
            },
            "semantic_reasoning": {
                "LLMFailure": {
                    "name": "rule_based_reasoning",
                    "handler": "RuleBasedReasoner",
                    "description": "Fallback to rule-based semantic analysis"
                }
            },
            "transformation": {
                "UnsupportedFunction": {
                    "name": "function_decomposition",
                    "handler": "FunctionDecomposer",
                    "description": "Decompose complex functions into simpler steps"
                },
                "TypeMismatch": {
                    "name": "type_coercion",
                    "handler": "TypeCoercer",
                    "description": "Coerce data types to match target"
                }
            },
            "export": {
                "FormatError": {
                    "name": "alternative_format",
                    "handler": "AlternativeFormatExporter",
                    "description": "Export to alternative format"
                }
            }
        }
    
    def get_fallback(self, step_name: str, error_type: str) -> Optional[Dict]:
        """Récupère un fallback pour une erreur donnée"""
        step_fallbacks = self.fallbacks.get(step_name, {})
        return step_fallbacks.get(error_type)
    
    def register_fallback(self, step_name: str, error_type: str, fallback: Dict):
        """Enregistre un nouveau fallback"""
        if step_name not in self.fallbacks:
            self.fallbacks[step_name] = {}
        self.fallbacks[step_name][error_type] = fallback

class SelfHealingOrchestrator(OrchestratorAgent):
    """
    Orchestrateur avec capacités de self-healing avancées
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.healing_engine = HealingEngine(config.get("healing", {}))
    
    async def _heal_failed_step(self, 
                                step: Dict, 
                                error: Exception, 
                                context: ExecutionContext) -> Optional[Any]:
        """
        Tente de guérir une étape qui a échoué
        """
        self.logger.info(f"Attempting to heal step {step.get('name')}")
        
        # 1. Analyser la cause
        root_cause = self.healing_engine.analyze_root_cause(error, step, context)
        
        # 2. Générer un plan de guérison
        healing_plan = self.healing_engine.generate_healing_plan(root_cause, step)
        
        # 3. Exécuter le plan
        healed_result = await self.healing_engine.execute_healing_plan(
            healing_plan, step, context
        )
        
        # 4. Enregistrer l'intervention
        self._record_healing_intervention(step, root_cause, healing_plan)
        
        return healed_result
    
    def _record_healing_intervention(self, step: Dict, root_cause: str, plan: Dict):
        """Enregistre une intervention de healing pour analyse future"""
        self.execution_history[-1].metadata.setdefault("healing_interventions", []).append({
            "step": step.get("name"),
            "root_cause": root_cause,
            "plan": plan,
            "timestamp": datetime.utcnow().isoformat()
        })

class HealingEngine:
    """Moteur de self-healing"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.patterns = self._load_healing_patterns()
    
    def analyze_root_cause(self, error: Exception, step: Dict, context: ExecutionContext) -> str:
        """Analyse la cause racine de l'erreur"""
        error_msg = str(error).lower()
        
        # Patterns de détection
        if "timeout" in error_msg or "time out" in error_msg:
            return "TIMEOUT"
        elif "memory" in error_msg or "out of memory" in error_msg:
            return "MEMORY_OVERFLOW"
        elif "schema" in error_msg or "type mismatch" in error_msg:
            return "SCHEMA_MISMATCH"
        elif "dependency" in error_msg or "missing" in error_msg:
            return "MISSING_DEPENDENCY"
        elif "permission" in error_msg or "access denied" in error_msg:
            return "PERMISSION_ERROR"
        else:
            return "UNKNOWN"
    
    def generate_healing_plan(self, root_cause: str, step: Dict) -> Dict:
        """Génère un plan de guérison basé sur la cause racine"""
        plans = {
            "TIMEOUT": {
                "actions": [
                    {"type": "increase_timeout", "value": step.get("timeout", 300) * 2},
                    {"type": "split_operation", "batch_size": 1000},
                    {"type": "retry_with_backoff", "max_retries": 3}
                ]
            },
            "MEMORY_OVERFLOW": {
                "actions": [
                    {"type": "stream_processing", "enabled": True},
                    {"type": "reduce_batch_size", "value": 500},
                    {"type": "use_disk_spill", "enabled": True}
                ]
            },
            "SCHEMA_MISMATCH": {
                "actions": [
                    {"type": "infer_schema_from_data", "enabled": True},
                    {"type": "apply_type_coercion", "strategy": "safe_cast"},
                    {"type": "log_warning_continue", "enabled": True}
                ]
            },
            "MISSING_DEPENDENCY": {
                "actions": [
                    {"type": "auto_install_dependency", "enabled": True},
                    {"type": "use_alternative_library", "fallback": True},
                    {"type": "skip_non_critical", "enabled": True}
                ]
            },
            "PERMISSION_ERROR": {
                "actions": [
                    {"type": "request_elevated_permissions", "interactive": True},
                    {"type": "use_alternative_location", "fallback": True},
                    {"type": "abort_with_instruction", "enabled": True}
                ]
            }
        }
        
        return plans.get(root_cause, {"actions": [{"type": "retry", "max_retries": 3}]})
    
    async def execute_healing_plan(self, plan: Dict, step: Dict, context: ExecutionContext) -> Any:
        """Exécute le plan de guérison"""
        # Modifier la configuration de l'étape selon le plan
        for action in plan.get("actions", []):
            if action["type"] == "increase_timeout":
                step["timeout"] = action["value"]
            elif action["type"] == "stream_processing":
                step["stream_mode"] = action["enabled"]
            # ... autres actions
        
        return None  # Retourner le résultat guéri
    
    def _load_healing_patterns(self) -> Dict:
        """Charge les patterns de healing"""
        return {}
```

## Partie 4 : Agent Factory et Configuration

```python
class AgentFactory:
    """
    Factory pour créer et configurer les agents
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("AgentFactory")
        self._agents_cache = {}
    
    def create(self, agent_type: AgentType) -> Any:
        """Crée une instance d'agent"""
        
        # Vérifier le cache
        if agent_type in self._agents_cache:
            return self._agents_cache[agent_type]
        
        agent_config = self.config.get(agent_type.value, {})
        
        # Créer l'agent selon le type
        if agent_type == AgentType.DATA_EXTRACTION:
            from agents.data_extraction import DataExtractionAgent
            agent = DataExtractionAgent(agent_config)
        
        elif agent_type == AgentType.PARSING:
            from agents.parsing import ParsingAgent
            agent = ParsingAgent(agent_config)
        
        elif agent_type == AgentType.SEMANTIC_REASONING:
            from agents.semantic_reasoning import SemanticReasoningAgent
            agent = SemanticReasoningAgent(agent_config)
        
        elif agent_type == AgentType.SPECIFICATION:
            from agents.specification import SpecificationAgent
            agent = SpecificationAgent(agent_config)
        
        elif agent_type == AgentType.TRANSFORMATION:
            from agents.transformation import TransformationAgent
            agent = TransformationAgent(agent_config)
        
        elif agent_type == AgentType.EXPORT:
            from agents.export import ExportAgent
            agent = ExportAgent(agent_config)
        
        elif agent_type == AgentType.VALIDATION:
            from agents.validation import ValidationAgent
            agent = ValidationAgent(agent_config)
        
        elif agent_type == AgentType.LINEAGE:
            from agents.lineage import LineageAgent
            agent = LineageAgent(agent_config)
        
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        # Mettre en cache
        self._agents_cache[agent_type] = agent
        
        return agent
    
    def register_agent(self, agent_type: AgentType, agent_class: type):
        """Enregistre un agent personnalisé"""
        self._custom_agents[agent_type] = agent_class

class PipelineValidator:
    """Validateur de pipelines"""
    
    def __init__(self, config: Dict):
        self.config = config
    
    def validate_pipeline(self, pipeline: PipelineDefinition, context: ExecutionContext) -> ValidationResult:
        """Valide un pipeline avant exécution"""
        issues = []
        
        # 1. Vérifier que les agents requis existent
        for step in pipeline.steps:
            agent_type = step.get("agent")
            if not agent_type:
                issues.append(f"Step {step.get('name')} has no agent specified")
        
        # 2. Vérifier les dépendances circulaires
        if self._has_circular_dependency(pipeline):
            issues.append("Circular dependency detected in pipeline")
        
        # 3. Vérifier la cohérence des inputs
        for step in pipeline.steps:
            inputs = step.get("inputs", {})
            required_inputs = step.get("required_inputs", [])
            for req in required_inputs:
                if req not in inputs and req not in ["artifacts", "context"]:
                    issues.append(f"Missing required input '{req}' for step {step.get('name')}")
        
        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            critical=len(issues) > 0
        )
    
    def _has_circular_dependency(self, pipeline: PipelineDefinition) -> bool:
        """Détecte les dépendances circulaires"""
        # Implémentation de détection de cycle dans le graphe de dépendances
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

@dataclass
class ValidationResult:
    is_valid: bool
    issues: List[str]
    critical: bool = False
```

## Partie 5 : Tests et Configuration

```python
# config/orchestrator_config.yaml
"""
orchestrator:
  max_retries: 3
  default_timeout: 300
  enable_parallel: true
  enable_self_healing: true
  
  pipeline:
    templates_path: "config/pipeline_templates"
    validation_enabled: true
  
  error_handling:
    max_retries: 3
    backoff_factor: 2
    fallback_enabled: true
  
  healing:
    enabled: true
    max_healing_attempts: 2
    record_interventions: true
  
  agents:
    data_extraction:
      max_rows: 1000000
      chunk_size: 10000
    
    parsing:
      use_llm_fallback: true
      max_file_size_mb: 500
    
    semantic_reasoning:
      llm_model: "gpt-4"
      confidence_threshold: 0.7
      use_fast_path: true
    
    specification:
      validation_strictness: "normal"
      include_confidence: true
    
    transformation:
      target_tools: ["powerbi", "tableau", "rdl"]
      optimization_level: "balanced"
    
    export:
      formats: ["rdl", "twbx", "pbix"]
      compress_output: true
"""

# tests/test_orchestrator.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

class TestOrchestratorAgent:
    
    @pytest.fixture
    def orchestrator(self):
        config = {
            "max_retries": 3,
            "default_timeout": 300,
            "enable_parallel": True,
            "enable_self_healing": True
        }
        return OrchestratorAgent(config)
    
    @pytest.fixture
    def sample_intent(self):
        return {
            "type": "conversion",
            "constraints": {
                "target_tool": "powerbi",
                "simplification": True
            },
            "plan": {
                "steps": ["extract", "parse", "transform", "export"]
            }
        }
    
    @pytest.fixture
    def sample_context(self):
        return {
            "user_id": "test_user",
            "preferences": {"language": "fr"},
            "session_id": "test_session"
        }
    
    @pytest.fixture
    def sample_artifacts(self):
        return {
            "files": ["dashboard.twb"],
            "data_sources": ["sales_db"]
        }
    
    @pytest.mark.asyncio
    async def test_orchestrate_conversion(self, orchestrator, sample_intent, sample_context, sample_artifacts):
        """Test d'orchestration d'une conversion"""
        
        # Mock des agents
        with patch.object(orchestrator, '_get_agent') as mock_get_agent:
            mock_agent = AsyncMock()
            mock_agent.execute = AsyncMock(return_value={"success": True})
            mock_get_agent.return_value = mock_agent
            
            # Exécuter
            result = await orchestrator.orchestrate(
                intent=sample_intent,
                context=sample_context,
                artifacts=sample_artifacts
            )
            
            # Vérifications
            assert result.status == ExecutionStatus.COMPLETED
            assert result.execution_id.startswith("exec_")
            assert len(result.results) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrate_with_error_recovery(self, orchestrator, sample_intent, sample_context, sample_artifacts):
        """Test de récupération après erreur"""
        
        call_count = 0
        
        async def mock_agent_execute(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("First attempt failed")
            return {"success": True}
        
        with patch.object(orchestrator, '_get_agent') as mock_get_agent:
            mock_agent = AsyncMock()
            mock_agent.execute = AsyncMock(side_effect=mock_agent_execute)
            mock_get_agent.return_value = mock_agent
            
            result = await orchestrator.orchestrate(
                intent=sample_intent,
                context=sample_context,
                artifacts=sample_artifacts
            )
            
            assert result.status == ExecutionStatus.COMPLETED
            assert call_count == 2  # Une erreur, un retry
    
    @pytest.mark.asyncio
    async def test_pipeline_builder_conversion(self, orchestrator, sample_intent, sample_context, sample_artifacts):
        """Test de construction de pipeline pour conversion"""
        
        pipeline = orchestrator.pipeline_builder.build(
            sample_intent, sample_context, sample_artifacts
        )
        
        assert pipeline.pipeline_id.startswith("pipeline_conversion")
        assert len(pipeline.steps) == 6  # Extraction, Parsing, Semantic, Specification, Transformation, Export
        assert pipeline.steps[0]["name"] == "data_extraction"
        assert pipeline.steps[-1]["name"] == "export"
    
    @pytest.mark.asyncio
    async def test_pipeline_builder_analysis(self, orchestrator):
        """Test de construction de pipeline pour analyse"""
        
        intent = {"type": "analysis", "constraints": {}}
        pipeline = orchestrator.pipeline_builder.build(intent, {}, {})
        
        assert len(pipeline.steps) == 3  # Extraction, Parsing (optional), Semantic
        assert pipeline.steps[0]["name"] == "data_extraction"
        assert pipeline.steps[-1]["name"] == "semantic_analysis"
    
    @pytest.mark.asyncio
    async def test_error_handler_retryable(self, orchestrator):
        """Test de détection d'erreur retryable"""
        
        error = TimeoutError("Connection timeout")
        step = {"name": "data_extraction", "required": True, "max_retries": 3}
        context = ExecutionContext(execution_id="test", intent={}, context={}, artifacts={})
        
        action = orchestrator.error_handler.handle_error(error, step, context, 0)
        
        assert action == RecoveryAction.RETRY
    
    @pytest.mark.asyncio
    async def test_error_handler_non_retryable(self, orchestrator):
        """Test d'erreur non retryable avec fallback"""
        
        error = ValidationError("Schema mismatch")
        step = {"name": "parsing", "required": True, "fallback_enabled": True}
        context = ExecutionContext(execution_id="test", intent={}, context={}, artifacts={})
        
        action = orchestrator.error_handler.handle_error(error, step, context, 3)
        
        assert action == RecoveryAction.FALLBACK
    
    def test_pipeline_validator_circular_dependency(self, orchestrator):
        """Test de détection de dépendance circulaire"""
        
        pipeline = PipelineDefinition(
            pipeline_id="test",
            steps=[
                {"name": "step_a", "depends_on": ["step_b"]},
                {"name": "step_b", "depends_on": ["step_a"]}
            ],
            parallel_groups=[],
            error_handling={},
            validation_points=[]
        )
        
        context = ExecutionContext(execution_id="test", intent={}, context={}, artifacts={})
        validation = orchestrator.validator.validate_pipeline(pipeline, context)
        
        assert not validation.is_valid
        assert "Circular dependency" in str(validation.issues)

# tests/test_integration.py
@pytest.mark.integration
class TestOrchestratorIntegration:
    
    @pytest.mark.asyncio
    async def test_end_to_end_conversion(self):
        """Test intégration complet de conversion Tableau -> Power BI"""
        
        # Configuration
        config = {
            "max_retries": 2,
            "enable_parallel": True,
            "agents": {
                "data_extraction": {"max_rows": 10000},
                "parsing": {"use_llm_fallback": True},
                "transformation": {"target_tools": ["powerbi"]}
            }
        }
        
        orchestrator = OrchestratorAgent(config)
        
        # Intent de conversion
        intent = {
            "type": "conversion",
            "constraints": {
                "target_tool": "powerbi",
                "simplification": True
            }
        }
        
        # Contexte utilisateur
        context = {
            "user_id": "test_user",
            "preferences": {"output_format": "pbix"}
        }
        
        # Artefacts
        artifacts = {
            "files": ["test_data/sample_dashboard.twb"],
            "data_sources": ["test_data/sample_sales.csv"]
        }
        
        # Exécution
        result = await orchestrator.orchestrate(intent, context, artifacts)
        
        # Vérifications
        assert result.status == ExecutionStatus.COMPLETED
        assert result.final_artifact is not None
        assert result.metrics["successful"] == 1
        
        print(f"Execution completed in {result.duration_ms}ms")
        print(f"Retries: {result.retries}")
        print(f"Validation issues: {len(result.validation_issues)}")
```

## Format de réponse attendu

Je souhaite recevoir une implémentation complète de l'Orchestrator Agent avec :

1. **Architecture complète** : classes principales et leurs responsabilités
2. **Pipeline Builder** : construction dynamique basée sur l'intention
3. **Error Handler** : gestion des erreurs et self-healing
4. **Agent Factory** : création et configuration des agents
5. **Pipeline Validator** : validation des pipelines avant exécution
6. **Configuration** : fichier YAML de configuration
7. **Tests unitaires et d'intégration** : exemples complets
8. **Documentation** : guide d'utilisation et d'extension

L'orchestrateur doit être capable de :
- Construire des pipelines adaptatifs selon l'intention
- Gérer l'exécution séquentielle et parallèle
- Détecter et corriger les erreurs de manière ciblée
- Maintenir la traçabilité complète des exécutions
- S'intégrer avec tous les agents précédemment développés
```