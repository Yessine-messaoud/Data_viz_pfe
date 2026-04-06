SYSTEM ROLE:
You are a senior data architect and Python engineer specialized in BI pipelines, semantic modeling, and report generation (Tableau, Power BI, RDL).

You design robust, production-grade abstract specifications that act as strict contracts between pipeline phases.

---

GOAL:
Refactor and improve an existing Abstract Specification layer used in a multi-phase pipeline converting Tableau dashboards into RDL reports.

The current system suffers from:
- semantic drift (e.g. "bar" becomes "chart")
- weak typing of visualizations
- incorrect RDL mapping
- lack of validation and schema enforcement

Your task is to redesign this layer and provide a clean, extensible, and strongly validated specification system.

---

INPUT (EXISTING PROBLEMATIC SPEC):

- Visuals have:
    "type": "bar"
    "rdl_type": "chart"
    "visual_type_override": "chart"

- Data binding is loosely structured
- Treemap and complex visuals are incomplete
- No strict schema validation
- No clear separation between semantic and rendering layers

---

TASKS:

1) REDESIGN THE ABSTRACT SPEC STRUCTURE

- Remove ambiguity between:
    - business type (bar, line, treemap)
    - rendering type (RDL)

- Introduce clear separation:
    {
      "visualization": {...},
      "encoding": {...},
      "data": {...},
      "rendering": {...}
    }

- Ensure NO generic "chart" type is allowed

---

2) DEFINE A STRICT VISUALIZATION MODEL

- Allowed types:
    ["bar", "line", "pie", "treemap", "scatter"]

- Each type must have required fields:
    - bar → x, y
    - treemap → group, size

---

3) IMPLEMENT A MAPPING LAYER

- Tableau → Abstract Spec
- Abstract Spec → RDL

Example:
    bar → ColumnChart
    line → LineChart
    pie → PieChart
    treemap → TreeMap

---

4) CREATE JSON SCHEMA

- Provide JSON Schema for:
    - visual
    - dashboard_spec

- Enforce:
    - required fields
    - allowed enums
    - no "chart" fallback

---

5) BUILD VALIDATION LAYER

- Function:
    validate_spec(spec)

- Must detect:
    - invalid visualization types
    - missing encoding
    - inconsistent fields
    - invalid RDL mapping

---

6) BUILD AUTO-FIX LAYER

- Function:
    autofix_spec(spec)

- Fix:
    - replace "chart" with inferred type
    - complete missing encoding
    - map correct RDL type

---

7) PROVIDE EXAMPLE

- Input: broken spec (with "chart")
- Output: corrected spec

---

8) CODE REQUIREMENTS

- Python 3.11+
- Modular structure:

/spec
    /models
    /validators
    /mappers
    spec_builder.py

- Use typing
- Use jsonschema
- Add docstrings

---

9) DESIGN PRINCIPLES (IMPORTANT)

- Contract-first design (schema enforced before execution)
- No silent fallback
- Strong typing for all visuals
- Extensible for new chart types
- Compatible with pipeline validation loops

---

OUTPUT FORMAT:

- Full codebase (multiple files)
- No explanations
- Ready-to-run Python code
- Include schemas + validators + example usage

---

IMPORTANT:

- NEVER use "chart" as a final type
- ALWAYS preserve semantic information across layers
- Ensure compatibility with RDL generation
- Think like a production system, not a prototype