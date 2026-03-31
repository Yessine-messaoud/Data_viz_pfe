You are a senior AI architect and data platform expert specializing in multi-agent systems, BI pipelines, and semantic data modeling.

## Context

I am building an agentic architecture for BI transformation and visualization. The system converts BI artifacts (Tableau, Power BI, RDL, CSV, databases) into a semantic representation and generates dashboards or reports.

The architecture is composed of:

* Conversation Agent (user interaction)
* Intent Detection Agent (intent understanding)
* Orchestrator Agent (dynamic pipeline control)
* Execution Agents (Data, Parsing, Semantic, Spec, Transformation, Export)
* Continuous Validation Agent (cross-cutting)
* Continuous Lineage Agent (cross-cutting)

## Focus of this task

You must evaluate and improve **Phase 0: Data Extraction**, which is currently implemented as a pipeline.

### Current Phase 0 Capabilities

* Detects data source types (Tableau Hyper, SQL, RDL)
* Extracts metadata: tables, columns, types, schemas, row counts
* Identifies columns used in dashboards (is_used_in_dashboard)
* Normalizes into a universal Pydantic model
* Performs optional profiling (distinct_count, null_ratio)
* Detects relationships (SQL foreign keys + heuristics like ID/Key)
* Builds a metadata catalog
* Exports JSON/YAML
* Uses a pipeline orchestrator with caching

## Task Requirements

### 1. Architecture Evaluation

Analyze the current Phase 0 and identify:

* Strengths (technical and architectural)
* Weaknesses (especially regarding agentic architecture)
* Missing capabilities
* Scalability issues
* Limitations in real-world BI scenarios

### 2. Agentic Transformation

Redesign Phase 0 as a **Data Extraction Agent**:

* Define its responsibilities
* Define its inputs/outputs
* Define how it interacts with:

  * Orchestrator Agent
  * Semantic Agent
  * Validation Agent (continuous)
  * Lineage Agent (continuous)

### 3. Advanced Improvements

Propose improvements such as:

* Dynamic strategy selection (rule-based vs LLM-based)
* Handling ambiguous schemas and relationships
* Confidence scoring for extracted metadata
* Error handling and retry strategies
* Partial extraction and incremental updates
* Schema evolution handling

### 4. Continuous Validation Integration

Explain how validation should be applied:

* After each sub-step
* What rules should be checked
* How errors should trigger corrections

### 5. Continuous Lineage Integration

Explain:

* What lineage information should be captured at this stage
* How it feeds the global lineage graph
* How it helps downstream agents

### 6. Output Design

Redesign the output of Phase 0 to be:

* Standardized
* Rich enough for Semantic Agent
* Compatible with agent orchestration

Provide a JSON schema example.

### 7. Self-Healing Mechanism

Describe:

* How the agent detects failure
* How it retries (alternative strategies)
* How it interacts with orchestrator for recovery

### 8. Real-world Scenarios

Evaluate how the system behaves in:

* Missing relationships
* Dirty data (nulls, duplicates)
* Large-scale datasets
* Complex enterprise schemas

### 9. Final Improved Architecture

Provide a refined architecture description for Phase 0 integrated in the global agentic system.

## Output Formatj

Structure your answer clearly using:

* Sections
* Bullet points
* Examples
* JSON where relevant

Be precise, technical, and critical. Avoid generic explanations.
