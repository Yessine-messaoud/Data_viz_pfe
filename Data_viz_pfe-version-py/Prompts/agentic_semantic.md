You are a senior AI architect and expert in semantic systems, knowledge graphs, and multi-agent architectures.

## Context

I am building an agentic BI transformation system that processes BI artifacts and generates dashboards. The system architecture includes:

* Conversation Agent
* Intent Detection Agent
* Orchestrator Agent
* Execution Agents:

  * Data Extraction Agent (Phase 0)
  * Parsing Agent (Phase 1)
  * Semantic Agent (Phase 2) ← THIS TASK
  * Specification Agent
  * Transformation Agent
  * Export Agent
* Cross-cutting:

  * Continuous Validation Agent
  * Continuous Lineage Agent

Phase 0 provides structured metadata (tables, columns, relationships, profiling).
Phase 1 provides parsed dashboard structure (visuals, filters, bindings, layout).

---

## Goal

Transform the current "semantic layer" into a fully **agentic Semantic Reasoning Agent** that:

* builds a semantic graph
* understands business meaning
* resolves ambiguities
* supports downstream generation
* dynamically decides between rule-based and LLM-based reasoning

---

## 1. Responsibilities of Semantic Agent

Define in detail what this agent must do:

* Build a semantic graph:

  * entities (tables, columns)
  * relationships
  * measures
  * business concepts (KPIs, dimensions, facts)
* Map parsed visuals to semantic meaning
* Detect business logic (aggregations, metrics)
* Infer missing relationships or concepts
* Resolve ambiguities (naming conflicts, unclear fields)

---

## 2. Agentic Behavior (CRITICAL)

Redesign the semantic layer as an intelligent agent with:

* decision-making capabilities
* strategy selection (fast path vs LLM path)
* confidence scoring
* fallback mechanisms

Explain:

* when to use deterministic rules
* when to invoke LLM reasoning
* how to minimize cost

---

## 3. Hybrid Reasoning Architecture

Design two main paths:

### A. Fast Path (Deterministic)

* rule-based mapping
* schema-driven inference
* naming conventions (e.g. *_id, *_date, revenue, amount)

### B. LLM Path (Advanced Reasoning)

* interpret ambiguous fields
* detect business meaning
* infer hidden relationships

Explain orchestration between both paths.

---

## 4. Semantic Graph Design

Define a graph structure including:

* Nodes:

  * Table
  * Column
  * Measure
  * KPI
  * Dimension
* Edges:

  * relationships (joins)
  * dependencies (measure uses columns)
  * visual bindings

Provide a JSON or graph representation example.

---

## 5. Input / Output Design

### Inputs:

* metadata from Phase 0
* parsed structure from Phase 1
* optional user intent (from orchestrator)

### Outputs:

* semantic graph
* enriched metadata
* inferred relationships
* confidence scores

Provide a detailed JSON output example.

---

## 6. Interaction with Other Agents

Explain how Semantic Agent interacts with:

* Parsing Agent (consume visual structure)
* Specification Agent (provide abstract model)
* Orchestrator Agent (receive strategy decisions)
* Validation Agent (continuous checks)
* Lineage Agent (trace semantic transformations)

---

## 7. Continuous Validation Integration

Define:

* semantic validation rules:

  * inconsistent joins
  * invalid aggregations
  * missing dimensions
* how validation feedback triggers reprocessing

---

## 8. Continuous Lineage Integration

Explain how semantic transformations are tracked:

* raw data → semantic concept → visual
* column → measure → KPI

Provide lineage examples.

---

## 9. Self-Healing Mechanisms

Design how the agent:

* detects ambiguity or low confidence
* retries with different strategies
* escalates to LLM
* updates graph incrementally

---

## 10. Advanced Features

Propose improvements such as:

* ontology or domain knowledge integration
* reusable semantic templates
* caching semantic interpretations
* incremental graph updates

---

## 11. Code-Level Design (IMPORTANT)

Provide a Python architecture:

* class SemanticAgent
* modules:

  * graph_builder
  * rule_engine
  * llm_reasoner
  * confidence_evaluator
* example methods:

  * build_graph()
  * infer_relationships()
  * resolve_ambiguity()
  * evaluate_confidence()

---

## 12. Real-world Scenarios

Explain behavior in:

* messy schemas (bad naming)
* missing relationships
* multiple data sources
* conflicting metrics definitions

---

## 13. Final Architecture Description

Provide a clean description of the Semantic Agent integrated into the full agentic system.

---

## Output Format

* structured sections
* technical explanations
* JSON examples
* Python pseudo-code

Be precise, practical, and critical. Avoid generic explanations.
