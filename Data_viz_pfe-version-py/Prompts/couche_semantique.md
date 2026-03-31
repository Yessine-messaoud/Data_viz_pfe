You are a senior software architect and data platform engineer.

I have an existing Python project that converts Tableau (.twbx) files into RDL reports using a multi-phase pipeline:

* Phase 0: Data extraction (Hyper/CSV)
* Phase 1: Tableau parsing
* Phase 2: Semantic layer (basic, LLM-assisted)
* Phase 3: Abstract Spec
* Phase 4: Calc translation
* Phase 5: RDL generation + validation
* Phase 6: Lineage export

The current semantic layer (phase2_semantic) is simplistic and not robust enough.

---

## 🎯 Objective

Refactor and upgrade the semantic layer into a **production-grade Semantic Intelligence Engine** with:

1. Data Profiling Engine
2. Ontology-based Semantic Mapping
3. Embedding + LLM hybrid mapping
4. Semantic Graph using Neo4j
5. Explainable and deterministic outputs

---

## ⚠️ Constraints

* Language: Python
* Keep existing pipeline structure but refactor phase2_semantic deeply
* Use Neo4j for graph storage
* Use Mistral API for LLM (API key MUST be manually written in code, not from env variables)
* Code must be modular, testable, and production-ready
* Avoid breaking existing phases (phase3, phase5 must still work)

---

## 🧱 Required Architecture

Refactor `phase2_semantic` into the following modules:

### 1. profiling/

* profile datasets using pandas
* classify columns:

  * measure
  * dimension
  * date
* compute stats: distinct count, null ratio

### 2. ontology/

* create a JSON-based ontology:

  * entities: Sales, Product, Customer, Geography, Time
  * metrics: Revenue, Quantity, Profit
* implement OntologyLoader class

### 3. mapping/

* create SemanticMappingEngine class
* combine:

  * heuristics (column name rules)
  * embeddings similarity
  * LLM validation (Mistral)
* output mapping with confidence score

### 4. llm/

* create mistral_client.py
* implement a function:

```python
def call_mistral(prompt: str) -> dict:
    # API key must be hardcoded manually in the file
    # do NOT use environment variables
```

* enforce JSON structured output

### 5. graph/

* integrate Neo4j using official driver

* create SemanticGraph class with:

  * create_nodes()
  * create_relationships()
  * query_graph()

* nodes:

  * Dataset
  * Column
  * BusinessTerm

* relationships:

  * MAPS_TO
  * BELONGS_TO
  * DERIVED_FROM

### 6. semantic_model/

* define Pydantic models:

  * ColumnProfile
  * SemanticMapping
  * SemanticModel

---

## 🔄 Pipeline Changes

Update phase 2 workflow:

1. Run profiling
2. Load ontology
3. Run mapping engine
4. Build semantic graph in Neo4j
5. Output enriched semantic model (JSON)

---

## 🧠 LLM Prompt Requirements

Use strict JSON prompts like:

{
"column": "...",
"possible_meaning": "...",
"mapped_business_term": "...",
"confidence": 0-1
}

---

## 🔐 Security Requirement

* Mistral API key must be written manually inside mistral_client.py like:

API_KEY = "REPLACE_WITH_KEY"

* Do not use .env or environment variables

---

## 🧪 Testing

* Add unit tests for:

  * profiling
  * mapping engine
  * graph creation

---

## 📦 Deliverables

* Refactored folder structure
* New modules implemented
* Updated phase2 entrypoint
* Example usage with a sample dataset
* Neo4j integration working locally

---

## 💡 Additional Requirements

* Add logging for each step
* Add confidence scoring for mappings
* Ensure deterministic fallback if LLM fails
* Keep code clean and documented

---

Now generate the full refactored code structure and key implementations.
