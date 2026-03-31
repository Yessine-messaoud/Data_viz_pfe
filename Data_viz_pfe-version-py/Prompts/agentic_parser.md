You are a senior software architect and AI engineer specializing in BI systems, semantic modeling, and multi-agent architectures.

## Context

I am building an agentic BI transformation system that processes BI artifacts (Tableau, Power BI, RDL, CSV, databases) and converts them into a semantic graph to generate or transform dashboards.

The system architecture includes:

* Conversation Agent
* Intent Detection Agent
* Orchestrator Agent
* Execution Agents:

  * Data Extraction Agent (Phase 0)
  * Parsing Agent (Phase 1) ← THIS TASK
  * Semantic Agent
  * Specification Agent
  * Transformation Agent
  * Export Agent
* Cross-cutting:

  * Continuous Validation Agent
  * Continuous Lineage Agent

Phase 0 already produces a normalized metadata model (tables, columns, relationships, profiling).

## Task

Design and specify **Phase 1: BI Parsing Agent**, which extracts all dashboard-level information from BI artifacts.

---

## 1. Objectives of Parsing Agent

Define clearly what this agent must extract from BI files such as:

* Tableau (.twb, .twbx)
* Power BI (if applicable)
* RDL (SSRS)

Include:

* visual elements (charts, tables, KPIs)
* layout structure (dashboard pages, positioning)
* filters (global, local)
* calculated fields / measures
* aggregations
* data bindings (which fields are used in which visuals)
* interactions between visuals (drill-down, cross-filtering)

---

## 2. Architecture Design

Redesign this phase as an **agent**, not a pipeline.

Define:

* Inputs (artifacts, metadata from Phase 0, context from orchestrator)
* Outputs (structured parsed representation)
* Internal modules (parsers, extractors, fallback mechanisms)

---

## 3. Parsing Strategy

Define a hybrid approach:

### A. Deterministic Parsing

* XML parsing for .twb and .rdl
* Structured extraction rules

### B. Heuristic Parsing

* Handle incomplete or inconsistent structures
* Infer missing bindings

### C. LLM-Assisted Parsing (optional but important)

* For ambiguous or complex structures
* For reconstructing logic not explicitly defined

Explain when each strategy is used.

---

## 4. Output Data Model

Design a **universal parsing model**, including:

* Dashboard
* Page / Sheet
* Visual
* Field bindings
* Filters
* Measures
* Layout (position, size)

Provide a JSON schema example like:

```json
{
  "dashboards": [
    {
      "name": "...",
      "pages": [...],
      "visuals": [...],
      "filters": [...]
    }
  ]
}
```

Make it rich enough for the Semantic Agent.

---

## 5. Interaction with Other Agents

Explain how Parsing Agent interacts with:

* Data Extraction Agent (Phase 0)
* Semantic Agent (Phase 2)
* Orchestrator Agent

---

## 6. Continuous Validation Integration

Define:

* validation rules after parsing
* examples of errors (missing fields, broken bindings)
* how the agent reacts (retry, fallback, correction)

---

## 7. Continuous Lineage Integration

Define what lineage information is captured:

* which visual uses which fields
* which filters impact which visuals
* mapping between data source and dashboard elements

Provide example lineage output.

---

## 8. Error Handling & Self-Healing

Design mechanisms for:

* partial parsing
* corrupted files
* unsupported features
* retry strategies (switch parser, use LLM)

---

## 9. Real-world Edge Cases

Explain how the agent handles:

* nested dashboards
* complex calculated fields
* multiple data sources
* hidden fields
* custom visuals

---

## 10. Code-Level Design (IMPORTANT)

Provide a clean Python architecture:

* class ParsingAgent
* modular components
* example methods:

  * parse_file()
  * extract_visuals()
  * extract_filters()
  * build_structure()

Use clean, production-like code structure.

---

## 11. Integration in Agentic System

Explain how this agent is invoked by the Orchestrator:

* based on intent
* conditional execution
* partial execution

---

## Output Format

* Use structured sections
* Include diagrams (if possible in text)
* Include JSON examples
* Include Python pseudo-code or real code

Be precise, technical, and practical. Avoid generic explanations.
