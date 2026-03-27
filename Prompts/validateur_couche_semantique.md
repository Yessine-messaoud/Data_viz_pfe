You are a senior data platform engineer.

I have a Python project that builds a semantic model from BI artifacts (Tableau → Semantic Model → RDL).
I need to implement a **production-grade Semantic Validator** that validates the output of my semantic layer before it is used by downstream phases.

---

## 🎯 Objective

Create a new module: `phase2b_validator` that validates a `SemanticModel` object.

The validator must be:

* deterministic first (rule-based)
* LLM-assisted (optional fallback using Mistral)
* robust, modular, and testable
* compatible with the existing pipeline

---

## 🧱 Input Model

Assume I have Pydantic models like:

```python
class ColumnProfile(BaseModel):
    name: str
    dtype: str
    role: str  # "measure" | "dimension" | "date"
    distinct_count: int
    null_ratio: float

class SemanticMapping(BaseModel):
    column_name: str
    mapped_to: str  # e.g. "Revenue", "Country"
    confidence: float

class SemanticModel(BaseModel):
    columns: list[ColumnProfile]
    mappings: list[SemanticMapping]
    relationships: list[dict]
```

---

## 🧪 Validation Requirements

### 1. Structural Validation

* Every column must have:

  * dtype
  * role
* Every mapping must have:

  * mapped_to
  * confidence

---

### 2. Business Rules Validation

Implement rules:

* measure → must be numeric (int, float)
* dimension → must NOT be numeric-dominant
* date → must be date/datetime

---

### 3. Ontology Validation

Assume we have a predefined ontology:

```python
VALID_BUSINESS_TERMS = [
    "Revenue", "Quantity", "Profit",
    "Country", "Product", "Category", "Date"
]
```

Rules:

* mapped_to must exist in ontology
* invalid mappings must be flagged

---

### 4. Confidence Validation

* if confidence < 0.6 → warning
* if confidence < 0.4 → error

---

### 5. Graph Validation (if relationships exist)

* no orphan nodes for critical entities (e.g. Revenue without dataset)
* relationships must contain valid keys:

  * source
  * target
  * type

---

## ⚙️ Output Format

Create a class:

```python
class ValidationResult(BaseModel):
    status: str  # "valid" | "warning" | "invalid"
    errors: list[str]
    warnings: list[str]
    score: float
```

---

## 🔧 Validator Design

Create class:

```python
class SemanticValidator:

    def validate(self, model: SemanticModel) -> ValidationResult:
        ...
```

Split logic into methods:

* validate_structure()
* validate_business_rules()
* validate_ontology()
* validate_confidence()
* validate_relationships()

---

## 🔁 Auto-Fix (IMPORTANT)

Add optional method:

```python
def auto_fix(self, model: SemanticModel) -> SemanticModel:
```

Examples:

* if measure is string → try casting
* if mapping missing → fallback to column name
* if confidence low → re-evaluate

---

## 🧠 LLM Integration (Mistral)

Create optional validation using LLM:

File: `llm_validator.py`

```python
def validate_with_llm(model_json: dict) -> dict:
    """
    Use Mistral API to check semantic coherence.
    API key MUST be hardcoded manually in this file.
    Return structured JSON.
    """
```

Prompt example:

"Check if the following semantic mappings are logically consistent. Return JSON with errors and warnings."

---

## 🔐 Security Constraint

* Mistral API key must be written manually in code:

```python
API_KEY = "REPLACE_WITH_KEY"
```

* Do NOT use environment variables

---

## 🧪 Testing

Create unit tests:

* test_valid_model()
* test_invalid_measure()
* test_low_confidence()
* test_invalid_mapping()

---

## 📦 Deliverables

* Complete `phase2b_validator` module
* Clean, modular code
* Logging included
* Example usage:

```python
validator = SemanticValidator()
result = validator.validate(model)

if result.status == "invalid":
    raise Exception("Semantic validation failed")
```

---

## 💡 Additional Requirements

* Add logging at each validation step
* Ensure no crash even if model is partially invalid
* Code must be production-ready and well documented

---

Now generate the full implementation.
