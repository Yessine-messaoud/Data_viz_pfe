SYSTEM ROLE:
You are a senior Python architect specialized in data pipelines, semantic layers, and LLM-based systems.
You write production-grade, modular, testable, and extensible code.

GOAL:
Generate a complete "Validation & AutoFix Layer" for a multi-phase data pipeline that processes Tableau artifacts into semantic models and RDL reports.

The system must implement continuous validation (syntax, semantic, structural) at each pipeline phase with automatic fixing capabilities.

CONTEXT:
The pipeline has the following phases:
0 - Extraction
1 - Parsing
2 - Semantic Layer
3 - Abstract Spec
3b - Validation (existing but limited)
4 - Transformation
5 - RDL Generation
6 - Lineage

The system already has:
- modular phases
- agent-based orchestration
- partial validation hooks
- partial self-healing

We want to upgrade this into a robust validation engine.

---

TASK:
Design and implement a full validation framework with:

1) VALIDATION ENGINE
- Central orchestrator: ValidationEngine
- Runs after each phase
- Accepts input/output artifacts
- Returns structured validation reports

2) VALIDATORS (modular)
- SyntaxValidator
- SemanticValidator
- StructuralValidator

Each validator must:
- expose validate(data, context)
- return structured errors:
  {
    "type": "syntax|semantic|structural",
    "severity": "warning|error",
    "message": "...",
    "location": "...",
    "suggestion": "..."
  }

3) AUTOFIX ENGINE
- Multi-level fixing system:
    a) rule-based fixes
    b) heuristic fixes (fuzzy matching, type correction)
    c) optional LLM-based fix (function stub only)

- Must re-run validation after fix

4) VALIDATION LOOP
Implement logic:

- validate → if errors → fix → revalidate
- max retry configurable
- fail if still invalid

5) SCHEMA VALIDATION
- Use JSON Schema for:
    - semantic model
    - abstract spec
- Provide example schemas

6) INTER-PHASE VALIDATION
- Validate consistency between phases
- Example:
    - fields in spec must exist in semantic model
    - RDL fields must match spec

7) QUALITY SCORING
Return a global score:
{
  "syntax_score": float,
  "semantic_score": float,
  "structural_score": float,
  "global_score": float
}

---

CONSTRAINTS:
- Python 3.11+
- Clean architecture (separation of concerns)
- No monolithic file
- Use typing
- Add docstrings
- Add minimal logging
- Avoid external heavy dependencies (except jsonschema, difflib)

---

OUTPUT FORMAT:
Return a full project structure:

/validation
    /validators
    /autofix
    /schemas
    validation_engine.py

For each file:
- provide full code
- no pseudo-code
- ready to run

---

EXTRA REQUIREMENTS:
- Include example usage in validation_engine.py
- Include one realistic validation case (broken spec → fixed spec)
- Make the system extensible (easy to add new validators)

---

IMPORTANT:
- Do NOT explain
- ONLY output code
- Ensure consistency across all modules
- Ensure imports work correctly