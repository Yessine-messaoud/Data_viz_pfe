You are a senior data engineer.

Problem:
The current system extracts data only from Tableau dashboard visuals (worksheets),
ignoring the underlying data sources (Hyper extract). This is incorrect.

Goal:
Refactor the pipeline so that ALL tables from the Tableau data source (.hyper or datasource section)
are treated as primary data sources in Power BI (RDL), NOT only the fields used in visuals.

--------------------------------------------------
REQUIRED FIXES
--------------------------------------------------

1. Hyper / Data Source Extraction (CRITICAL)

- Parse ALL tables from:
  - Tableau .hyper extract (if present)
  - OR datasource XML in .twb

- Build a complete list of tables:
  {
    table_name,
    columns: [{ name, type }],
    sample_data (first 5 rows)
  }

- DO NOT restrict to columns used in visuals.

--------------------------------------------------

2. Update Semantic Layer

- Modify SemanticModel to include ALL detected tables:
  semantic_model.entities = all_tables_from_hyper

- Keep visual usage as a subset:
  visual_column_map ⊂ full dataset

--------------------------------------------------

3. Update DataLineageSpec

- Add:
  full_tables: TableRef[]
  sampled_rows: Record<table_name, Row[]>

- Ensure lineage tracks:
  - full dataset
  - visual usage separately

--------------------------------------------------

4. Update Export (Power BI RDL)

- All extracted tables must be:
  - available as datasets in Power BI
  - not only visual-driven queries

- Generate one dataset per table:
  Dataset_<table_name>

--------------------------------------------------

5. HTML Debug Output (VERY IMPORTANT)

Extend the existing HTML report to include:

For EACH detected table:

- Table name
- Column list
- FIRST 5 ROWS (preview table)

Example:

=== TABLE: Sales ===
Columns: id, date, amount, customer_id

Preview:
| id | date       | amount | customer_id |
|----|-----------|--------|-------------|
| 1  | 2023-01-01 | 100    | 10          |
| ... (5 rows)

--------------------------------------------------

6. Add Function

createTablePreviewHTML(tables):

- Input: list of tables with sample_data
- Output: formatted HTML string
- Render all tables in sections
- Use clean table formatting

--------------------------------------------------

7. Validation Rules

- FAIL if no tables detected from datasource
- WARN if table has no sample data
- WARN if visual uses column not in extracted tables

--------------------------------------------------

8. Logging

Add logs:

- number of tables detected
- number of columns per table
- whether source is hyper or xml
- preview generated

--------------------------------------------------

9. Tests

- Test extraction from .twb with datasource
- Test extraction from .twbx with hyper
- Test HTML preview generation
- Test consistency:
  visual columns must exist in extracted tables

--------------------------------------------------

EXPECTED RESULT

- Full dataset awareness (not only visuals)
- Power BI datasets = real source tables
- HTML debug shows 5 rows per table
- Semantic layer enriched with full schema