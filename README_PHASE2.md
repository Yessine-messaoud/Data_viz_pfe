# README_PHASE2 - Couche Semantique Hybride

## 1) Objectif de la phase 2

La phase 2 transforme les metadonnees Tableau parsees (phase 1) en un modele semantique exploitable pour:
- construire un Abstract Spec coherent (phase 3),
- traduire les calculs (phase 4),
- generer un RDL valide et interpretable metier (phase 5),
- exposer un graphe semantique pour la gouvernance et le lineage avance.

En sortie, elle produit:
- `semantic_model` (mesures, dimensions, fact table, grain),
- `lineage` (tables, colonnes, joins),
- `phase2_artifacts` (ontology, mappings, profiles, graph payload + statut persistence Neo4j).

## 2) Architecture de la couche semantique

Implementation principale:
- `viz_agent/phase2_semantic/phase2_orchestrator.py`
- `viz_agent/phase2_semantic/hybrid_semantic_layer.py`

Sous-composants:
- Profiling:
  - `profiling/column_profiler.py`
- Mapping schema + joins:
  - `schema_mapper.py`
  - `join_resolver.py`
- Enrichissement metier:
  - `semantic_enricher.py` (LLM Mistral)
  - `semantic_merger.py` (fusion deterministe)
- Fact table et hygiene mesures:
  - `fact_table_detector.py`
- Ontologie metier:
  - `ontology/business_ontology.json`
  - `ontology/ontology_loader.py`
- Mapping semantique hybride:
  - `mapping/semantic_mapping_engine.py`
- Graphe semantique:
  - `graph/semantic_graph.py`

### Flux interne simplifie

1. `TableauSchemaMapper` construit les tables/colonnes
2. `JoinResolver` derive les relations inter-tables
3. `ColumnProfiler` calcule stats de qualite (si frames disponibles)
4. `SemanticEnricher` propose labels/mesures/hierarchies via LLM
5. `SemanticMerger` consolide en `SemanticModel`
6. `detect_fact_table` + `filter_fk_measures` finalisent le coeur metier
7. `OntologyLoader` charge et valide l ontologie
8. `SemanticMappingEngine` mappe colonnes -> termes metier avec score de confiance
9. `SemanticGraph.build_payload` prepare noeuds/relations
10. Optionnel: `SemanticGraph.from_env()` persiste le payload dans Neo4j

## 3) Approche hybride (deterministe + LLM)

La couche semantique suit une strategie hybride:

- Deterministe en priorite:
  - mapping schema,
  - resolution joins,
  - detection fact table,
  - filtrage des mesures de type FK,
  - fallback `unmapped` si confiance insuffisante.

- LLM cible et borne:
  - enrichissement metier (labels, mesures suggerees, hierarchies),
  - validation contextuelle de mapping.

- Gouvernance par score:
  - score de confiance par mapping,
  - seuil minimal (`min_confidence`) avant acceptation,
  - details de provenance (`heuristic`, `embedding`, `llm`) conserves.

Cette approche combine robustesse operationnelle (determinisme) et richesse semantique (LLM).

## 4) Points forts de la phase 2

1. Robustesse production
- Loader d ontologie valide le schema JSON et merge proprement avec deduplication.
- Mapping resilient meme si `scikit-learn` est indisponible.

2. Explainabilite
- Chaque mapping contient `details` (score et methode).
- Le payload de graphe est explicite (`Table`, `Column`, `Measure`, `BusinessTerm`).

3. Extensibilite
- Orchestrateur dedie (`Phase2SemanticOrchestrator`) isolant la phase 2.
- Ontologie surchargeable via `VIZ_AGENT_ONTOLOGY_PATH`.

4. Interoperabilite pipeline
- Sortie `semantic_model` compatible phases 3/5.
- Export `X_semantic_model.json` exploitable par outillage externe.

5. Gouvernance et lineage avance
- Neo4j optionnel pour requetage semantique transversal.
- Relations utiles: `HAS_COLUMN`, `JOINS_TO`, `DERIVED_FROM`, `MAPPED_TO`.

## 5) Workflow recommande (phase 2)

### A) Pre-conditions
- Phase 0 terminee (frames accessibles via `DataSourceRegistry`)
- Phase 1 terminee (`ParsedWorkbook` disponible)
- `MISTRAL_API_KEY` defini si enrichissement LLM actif

### B) Execution via orchestrateur
- Entree: `ParsedWorkbook`, intent
- Appel: `Phase2SemanticOrchestrator.run(workbook, intent)`
- Sortie:
  - `semantic_model`
  - `lineage`
  - `phase2_artifacts`

### C) Post-conditions
- `fact_table` renseignee
- mesures nettoyees (FK retirees)
- mappings semantiques disponibles
- graph payload construit
- persistence Neo4j effectuee ou skippee proprement selon config

## 6) Outils, librairies et technologies

- Python 3.11+
- `pandas`: profiling et stats de colonnes
- `pydantic`: modeles et validation
- `scikit-learn`: TF-IDF + similarite cosine pour matching semantique
- `neo4j` driver: persistence du graphe semantique
- `requests` / client Mistral: appels LLM
- `pytest`: tests unitaires et integration

## 7) Configuration operationnelle

Variables d environnement principales:

- LLM:
  - `MISTRAL_API_KEY`
  - `MISTRAL_MODEL`
  - `MISTRAL_BASE_URL`

- Ontologie:
  - `VIZ_AGENT_ONTOLOGY_PATH` (optionnel)

- Graphe Neo4j:
  - `VIZ_AGENT_SEMANTIC_GRAPH_ENABLED` (`true/1` pour activer)
  - `VIZ_AGENT_NEO4J_URI` (defaut `bolt://localhost:7687`)
  - `VIZ_AGENT_NEO4J_USER` (defaut `neo4j`)
  - `VIZ_AGENT_NEO4J_PASSWORD` (obligatoire si active)

## 8) Artefact cible: semantic model exporte

Le pipeline ecrit `X_semantic_model.json` contenant:

- `semantic_model`
  - mesures
  - dimensions
  - fact_table
  - grain
- `phase2_artifacts`
  - `ontology`
  - `mappings`
  - `column_profiles`
  - `graph`
    - `nodes`
    - `relationships`
    - `persisted`
    - `error`

## 9) Qualite et tests

Couverture phase 2:
- ontology loader
- mapping engine
- graph payload
- compatibilite phase2 -> phase3
- integration Neo4j locale (conditionnelle)

Commandes utiles:

```powershell
python -m pytest tests/phase2_semantic -q
python -m pytest viz_agent/tests/test_phase2.py viz_agent/tests/test_phase3.py viz_agent/tests/test_phase5_rdl.py -q
```

## 10) Limites actuelles et evolutions possibles

1. Mapping contextuel multi-table
- ambiguite possible si meme nom de colonne dans plusieurs tables.

2. Ontologie dynamique
- enrichissement automatique des termes metier possibles via retours d usage.

3. Graph analytics
- ajout de requetes predefinies (impact analysis, lineage metrique, mapping drift).

4. Scoring avance
- calibration du score de confiance par domaine (finance, ventes, supply).
