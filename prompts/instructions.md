You are a senior TypeScript/Python data engineer.

Goal:
Build the core of an AI visualization agent that converts Tableau dashboards (.twb/.twbx) into Power BI (.pbix) with full data lineage and reproducibility.

Architecture constraint:
The system is centered around a strongly-typed AbstractSpec which is the SINGLE SOURCE OF TRUTH.
All downstream components MUST consume AbstractSpec.

Rules:
- Start STRICTLY with Phase 0 (AbstractSpec)
- Each task = isolated PR (small, testable)
- Use TypeScript strict mode (no `any`)
- Define interfaces BEFORE implementations
- Add unit tests for every module
- DataLineageSpec MUST be built during semantic phase (NOT post-processing)

--------------------------------------------------
PHASE 0 — AbstractSpec (CRITICAL CORE)
--------------------------------------------------

Task 0.1 — Define AbstractSpec root type
Fields:
- id: stable UUID
- version: semver
- source_fingerprint: SHA-256
- dashboard_spec
- semantic_model
- data_lineage
- export_manifest
- build_log
- warnings

Task 0.2 — DashboardSpec
- pages[]
- global_filters[]
- theme: ThemeConfig
- refresh_policy

Task 0.3 — VisualSpec + DataBinding
- id
- source_worksheet (Tableau reference)
- type: VisualType
- position: GridPosition
- data_binding.axes:
  { x?, y?, color?, size?, tooltip? } → ColumnRef

Task 0.4 — DataLineageSpec
- tables: TableRef[]
- joins: JoinDef[]
- columns_used: ColumnUsage[]
- visual_column_map:
  Record<visual_id, { columns, joins_used, filters }>

Task 0.5 — SemanticModel
- entities
- measures
- dimensions
- hierarchies
- relationships
- glossary
- fact_table
- grain

Task 0.6 — ExportManifest
- target: "powerbi"
- model_config
- dax_measures
- m_queries
- post_export_hooks

Task 0.7 — AbstractSpecBuilder
Function:
build(workbook, intent, semantic_model, lineage): AbstractSpec

Requirements:
- SHA-256 fingerprint from workbook
- deterministic UUID generation
- full spec assembly

Task 0.8 — Unit Tests
- JSON serialize/deserialize (no loss)
- stable IDs across builds

--------------------------------------------------
PHASE 1–2 — Tableau Input & Parsing
--------------------------------------------------

Task 1.1 — TableauParser
- Parse .twb XML → ParsedWorkbook
- Extract:
  worksheets (rows/cols/marks/filters)
  datasources (tables, columns, types)
  calculated_fields
  dashboards (layout, zones)
  parameters

Task 1.2 — TWBX support
- unzip
- extract .twb + data (hyper/csv)

Task 1.3 — IntentClassifier (LLM)
Input: natural language request
Output:
{
  action,
  target: "powerbi",
  modifications[],
  confidence
}

Task 1.4 — AgentRequest
- Merge ParsedWorkbook + Intent + config

--------------------------------------------------
PHASE 4 — Hybrid Semantic Layer
--------------------------------------------------

Two branches:
- Deterministic (structure)
- LLM (semantic enrichment)

Task 4.1 — SchemaMapper
- Type mapping Tableau → Power BI
- Visual mapping (bar → clustered bar, etc.)

Task 4.2 — SemanticEnricher (LLM)
- rename columns
- suggest missing measures
- resolve ambiguities

Task 4.3 — CalcFieldTranslator
- Tableau formulas → DAX
- Templates for simple aggregations
- LLM for LOD & table calculations

Task 4.4 — JoinResolver
- Parse joins from Tableau XML
- Output JoinDef with Power BI relationship mapping

Task 4.5 — SemanticMerger
- deterministic > structure
- LLM > semantics
- add confidence scoring
- glossary override priority

--------------------------------------------------
PHASE 5 — Transformation Engine
--------------------------------------------------

Task 5.1 — TransformPlanner
- Convert intent.modifications → ordered TransformOps

Task 5.2 — StarSchemaBuilder
- Detect fact table
- Build dimension tables
- Generate bridge tables (M:N)
- Auto Date dimension

Task 5.3 — MQueryBuilder
- Generate Power Query M
- Map TransformOps → M steps

Task 5.4 — DAXGenerator
- Templates for basic measures
- LLM for complex calculations

--------------------------------------------------
PHASE 6 — Power BI Export Adapter
--------------------------------------------------

Task 6.1 — ITargetAdapter (interface)
- validate()
- build()
- deploy()
- getCapabilities()

Task 6.2 — PowerBIAdapter
- validate model + DAX
- build pbix artifacts (model + layout)
- deploy via API

Task 6.3 — PBIXAssembler
- ZIP structure:
  DataModel/
  Report/
  theme.json
  connections

Task 6.4 — AdapterRegistry
- register/resolve adapters

--------------------------------------------------
PHASE 7 — Data Lineage & Traceability
--------------------------------------------------

Task 7.1 — lineage.json structure
- tables
- joins
- visual_column_map
- measures
- sql_equivalents

Task 7.2 — LineageQueryService
- getTablesForVisual()
- getJoin()
- getVisualsForColumn()

Task 7.3 — generateSQL(visual_id)
- reconstruct SQL from lineage

Task 7.4 — VizAgentCore.run()
Pipeline:
parse → semantic → spec → transform → export → lineage

Output:
{
  artifact,
  spec,
  lineage,
  url
}