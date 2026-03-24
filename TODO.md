# TODO - Agent de visualisation Tableau -> Power BI

## Phase 0 - AbstractSpec (ordre strict)
- [x] Task 0.1 - Definir le type racine AbstractSpec
- [x] Task 0.2 - Definir DashboardSpec
- [x] Task 0.3 - Definir VisualSpec + DataBinding
- [x] Task 0.4 - Definir DataLineageSpec
- [x] Task 0.5 - Definir SemanticModel
- [x] Task 0.6 - Definir ExportManifest
- [x] Task 0.7 - Implementer AbstractSpecBuilder
- [x] Task 0.8 - Ajouter les tests unitaires

## Phase 1-2 - Tableau input & parsing
- [x] Task 1.1 - Implementer TableauParser (.twb XML -> ParsedWorkbook)
- [x] Task 1.2 - Ajouter support TWBX (unzip + extraction)
- [x] Task 1.3 - Implementer IntentClassifier (LLM)
- [x] Task 1.4 - Implementer AgentRequest (merge workbook + intent + config)

## Phase 4 - Hybrid semantic layer
- [x] Task 4.1 - Implementer SchemaMapper
- [x] Task 4.2 - Implementer SemanticEnricher (LLM)
- [x] Task 4.3 - Implementer CalcFieldTranslator
- [x] Task 4.4 - Implementer JoinResolver
- [x] Task 4.5 - Implementer SemanticMerger

## Phase 5 - Transformation engine
- [x] Task 5.1 - Implementer TransformPlanner
- [x] Task 5.2 - Implementer StarSchemaBuilder
- [x] Task 5.3 - Implementer MQueryBuilder
- [x] Task 5.4 - Implementer DAXGenerator

## Phase 6 - Power BI export adapter
- [x] Task 6.1 - Definir ITargetAdapter
- [x] Task 6.2 - Implementer PowerBIAdapter
- [x] Task 6.3 - Implementer PBIXAssembler
- [x] Task 6.4 - Implementer AdapterRegistry

## Phase 7 - Data lineage & traceability
- [x] Task 7.1 - Definir structure lineage.json
- [x] Task 7.2 - Implementer LineageQueryService
- [x] Task 7.3 - Implementer generateSQL(visual_id)
- [x] Task 7.4 - Implementer VizAgentCore.run()
