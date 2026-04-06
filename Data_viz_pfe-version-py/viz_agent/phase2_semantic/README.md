# Phase 2 - Hybrid Semantic Layer

## 1. But de la phase

La phase semantique transforme le workbook parse (phase 1) en une representation metier exploitable par les phases suivantes.

Objectifs:

- construire un `SemanticModel` coherent (entites, mesures, dimensions, hierarchies)
- produire un `DataLineageSpec` minimal (tables + joins)
- enrichir avec des artefacts de raisonnement (`ontology`, `mappings`, `column_profiles`, `graph`)
- preparer des sorties robustes meme si certains sous-modules echouent (profiling/mapping non bloquants)

Sortie principale de l'orchestrateur phase 2:

- tuple `(semantic_model, lineage, phase2_artifacts)`

---

## 2. Point d'entree et orchestration

### 2.1 Entrypoint

Fichier: `phase2_orchestrator.py`

- `Phase2SemanticOrchestrator.run(workbook, intent=None)`
- delegue a `HybridSemanticLayer.enrich_with_artifacts(...)`

### 2.2 Nouvelle orchestration agentique (3 paths)

Fichiers:

- `hybrid_semantic_layer.py`
- `agentic_semantic_orchestrator.py`

L'orchestrateur applique la strategie suivante:

1. Cache path
: reutilise un resultat semantique recent si le fingerprint input+intent est deja present en cache.

2. Fast path (obligatoire)
: execution deterministe, stable, ultra-rapide, basee sur:
- dtype
- conventions de nommage
- regles heuristiques simples

3. Fallback path
: active uniquement si la confidence du fast path est inferieure au seuil (85% par defaut).

### 2.3 Formule de confidence (avec normalisation dynamique)

La confidence globale est calculee avec une **normalisation dynamique** des poids:

- **Poids initiaux** (configuration de base):
  - `heuristic_score`: 0.4 (40%)
  - `profiling_score`: 0.2 (20%)
  - `ontology_score`: 0.2 (20%)
  - `llm_score`: 0.2 (20%)

- **Normalisation**: Si un composant a un score de **0.0**, il est **exclu** de la formule et les poids des autres composants sont **renormalisés** proportionnellement.

**Exemple**: Si `llm_score = 0.0` (LLM non utilisé):
```text
total_weight = 0.4 + 0.2 + 0.2 = 0.8  (le poids 0.2 de llm est exclu)
confidence = (0.4 * heuristic + 0.2 * profiling + 0.2 * ontology) / 0.8
```

**Interprétation**: La confidence est toujours une moyenne pondérée des composants disponibles, jamais diluée par des poids inutilisés.

Seuil par defaut:

- `0.85` (configurable via variable d'environnement `VIZ_AGENT_SEMANTIC_CONFIDENCE_THRESHOLD`)

### 2.4 Sous-etapes techniques executees

Dans les paths `fast` et `fallback`, l'ordre de base est:

1. `TableauSchemaMapper.map(workbook)`
: construit un schema unifie de tables/colonnes.

2. `JoinResolver.resolve(workbook.datasources)`
: genere une liste de joins (heuristique actuelle, sequentiale).

3. Profiling colonnes (best effort)
: si `workbook.data_registry` contient des frames (Hyper/CSV), calcule profils colonnes via `ColumnProfiler`.

4. Enrichissement semantique LLM/heuristique
: `SemanticEnricher.enrich(workbook, schema_map)`.

5. Fusion semantique
: `SemanticMerger.merge(schema_map, llm_enrichment)`.

6. Post-traitements metier
: detection fact table (`detect_fact_table`) + filtrage mesures FK (`filter_fk_measures`).

7. Mapping ontologique hybride
: `OntologyLoader.load()` puis `SemanticMappingEngine.map_columns(...)`.

8. Construction lineage
: creation `DataLineageSpec(tables, joins, columns_used=[])`.

9. Construction graphe semantique
: `SemanticGraph.build_payload(...)` puis persistence optionnelle Neo4j.

10. Assemblage des artefacts
: objet `phase2_artifacts` retourne au pipeline global.

---

## 3. Composants et responsabilites

### 3.1 Schema mapping

Fichier: `schema_mapper.py`

- priorite aux donnees extraites (`registry.all_frames()`) si disponibles
- sinon fallback sur `workbook.datasources`
- fusion des tables de meme nom via `_merge_table`
- infere role de colonne:
	- `measure` si dtype `int64/float64`
	- `dimension` sinon

### 3.2 Join resolution

Fichier: `join_resolver.py`

- implemente un chainage heuristique entre datasources consecutives
- genere des `JoinDef` avec `left_col='id'` et `right_col='id'`
- limitation actuelle: pas de parsing detaille des joins SQL natifs

### 3.3 Profiling colonnes

Fichier: `profiling/column_profiler.py`

- calcule pour chaque colonne:
	- `inferred_dtype`
	- `role` (`measure` / `dimension` / `date`)
	- `distinct_count`
	- `null_ratio`
	- `sample_values`
- non bloquant: en cas d'erreur, la phase continue

### 3.4 Enrichissement semantique (LLM + fallback)

Fichier: `semantic_enricher.py`

- construit un prompt a partir de:
	- tables/colonnes
	- calculated fields
	- worksheets (rows/cols/marks)
	- dashboards
- attend une reponse JSON:
	- `column_labels`
	- `suggested_measures`
	- `hierarchies`
	- `column_roles`
- fallback heuristique si pas de mesures LLM:
	- champs calcules
	- colonnes candidates numeriques/metier
	- fallback final `Row Count`

Client LLM par defaut:

- `LLMFallbackClient` (`llm_fallback_client.py`)
- chaine de fallback selon configuration env (Mistral/Gemini/Ollama)

### 3.5 Semantic merge

Fichier: `semantic_merger.py`

- applique labels/roles enrichis sur les colonnes
- construit:
	- `entities` (tables)
	- `measures`
	- `dimensions` (colonnes non mesures)
	- `hierarchies`

### 3.6 Fact table detection et filtrage mesures FK

Fichier: `fact_table_detector.py`

- score combine:
	- indices FK
	- mots-cles de mesures
	- participation joins
- exclut certaines tables candidates (`date_data`, `excel_direct_data`)
- supprime les mesures de type FK via regex patterns

### 3.7 Ontology loading

Fichier: `ontology/ontology_loader.py`

- charge ontologie par defaut (inline) ou depuis fichier externe
- merge base + override utilisateur
- validation schema JSON

### 3.8 Semantic mapping engine

Fichier: `mapping/semantic_mapping_engine.py`

- combine 3 signaux:
	- heuristique (alias/substring)
	- embedding TF-IDF (si `scikit-learn` dispo)
	- validation LLM optionnelle
- retourne une liste de `SemanticMappingModel`
- degrade proprement si embedding indisponible

### 3.9 Semantic graph

Fichier: `graph/semantic_graph.py`

- construit un payload JSON normalise:
	- `nodes`
	- `relationships`
- noeuds incluent desormais explicitement:
	- `id`
	- `type`
	- `label` (compatibilite)
- relations incluent `type` (`HAS_COLUMN`, `JOINS_TO`, `DERIVED_FROM`, `MAPPED_TO`, ...)
- deduplication pour stabiliser les sorties
- persistence Neo4j optionnelle via `from_env()`

---

## 4. Sous-etapes detaillees (vue operationnelle)

### Etape A - Preparation schema

Entree:

- `ParsedWorkbook`

Sortie:

- `schema_map.tables`

### Etape B - Calcul joins

Entree:

- `workbook.datasources`

Sortie:

- `joins: list[JoinDef]`

### Etape C - Profiling (optionnel)

Entree:

- `workbook.data_registry.all_frames()`

Sortie:

- `column_profiles` (artefact)

### Etape D - Enrichissement semantique

Entree:

- schema + contexte workbook (worksheets/dashboards/calculated fields)

Sortie:

- labels colonnes
- mesures proposees
- hierarchies
- roles colonnes

### Etape E - Fusion + regles metier

Sortie:

- `semantic_model`
- `fact_table`
- `measures` filtrees

### Etape F - Mapping ontologie

Sortie:

- `mappings` (score, methode, details)

### Etape G - Construction lineage + graph

Sortie:

- `lineage`
- `graph.nodes`
- `graph.relationships`
- `graph.persisted`
- `graph.error`

---

## 5. Artefacts produits

Structure `phase2_artifacts`:

```json
{
	"ontology": {"entities": [], "metrics": [], "terms": []},
	"mappings": [
		{
			"column": "SalesAmount",
			"mapped_business_term": "Sales",
			"confidence": 0.9,
			"method": "heuristic",
			"details": {}
		}
	],
	"column_profiles": {
		"table_name": [
			{
				"name": "SalesAmount",
				"inferred_dtype": "float64",
				"role": "measure",
				"distinct_count": 100,
				"null_ratio": 0.0,
				"sample_values": [1.0, 2.0, 3.0]
			}
		]
	},
	"graph": {
		"nodes": [{"id": "table:...", "type": "Table", "label": "Table"}],
		"relationships": [{"source_id": "...", "target_id": "...", "type": "HAS_COLUMN"}],
		"persisted": false,
		"error": ""
	},
	"orchestration": {
		"selected_path": "fast|fallback|cache",
		"threshold": 0.85,
		"confidence": 0.91,
		"confidence_components": {
			"heuristic_score": 0.95,
			"profiling_score": 0.90,
			"ontology_score": 0.85,
			"llm_score": 0.80
		}
	}
}
```

---

## 6. Configuration (variables d'environnement)

### 6.1 LLM

- `MISTRAL_API_KEY`
- `GEMINI_API_KEY`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `VIZ_AGENT_API_KEY_FILE`

### 6.2 Ontologie

- `VIZ_AGENT_ONTOLOGY_PATH`

### 6.3 Orchestration agentique et cache

- `VIZ_AGENT_SEMANTIC_CONFIDENCE_THRESHOLD` (defaut `0.85`)
- `VIZ_AGENT_SEMANTIC_CACHE_TTL_SECONDS` (defaut `21600`)
- `VIZ_AGENT_SEMANTIC_CACHE_DIR` (defaut `.vizagent_cache/phase2_semantic`)

### 6.4 Persistence graphe Neo4j

- `VIZ_AGENT_SEMANTIC_GRAPH_ENABLED=true`
- `VIZ_AGENT_NEO4J_URI=bolt://localhost:7687`
- `VIZ_AGENT_NEO4J_USER=neo4j`
- `VIZ_AGENT_NEO4J_PASSWORD=...`

---

## 7. Composants agentiques existants (statut)

Le dossier `agent/` contient une architecture agentique separee:

- `semantic_agent.py`
- `graph_builder.py`
- `rule_engine.py`
- `llm_reasoner.py`
- `confidence_evaluator.py`
- `validation_hook.py`
- `lineage_hook.py`

Statut actuel:

- les classes existent et definissent la structure
- certaines briques sont encore des placeholders (`TODO`) dans `graph_builder.py`, `rule_engine.py`, `llm_reasoner.py`
- le pipeline principal de prod passe aujourd'hui par `phase2_orchestrator.py` + `hybrid_semantic_layer.py`

---

## 8. Gestion d'erreurs et resilence

- Profiling: erreurs capturees, pipeline continue
- Mapping ontologie: erreurs capturees, pipeline continue
- Persistence Neo4j: non bloquante (erreur retournee dans `graph.error`)
- Enrichissement LLM: fallback heuristique mesures si reponse vide/invalide

---

## 9. Exemples d'execution

### 9.1 Via pipeline complet

```powershell
python -m viz_agent.main --input input/demo1.2.twbx --output output/demo1_2_complete.rdl
```

### 9.2 Demo centree semantic graph

```powershell
python demo_semantic_graph.py --input input --graph-dir output/semantic_graph --report-json output/semantic_graph_report.json --report-html output/semantic_graph_report.html
```

---

## 10. Limites actuelles connues

- `JoinResolver` encore heuristique (joins `id -> id`)
- dependance a la qualite des noms de colonnes pour certaines inférences
- mapping LLM reseau potentiellement lent si active
- branche `agent/` historique partiellement implementee (distincte de l'orchestrateur agentique principal)

---

## 11. Extensions recommandees

- brancher un resolveur de joins base sur SQL lineage reel
- ajouter normalisation des types PBI via dictionnaire central
- enrichir dimensions/hierarchies temps par detection calendrier explicite
- ajouter tests non-regression sur `phase2_artifacts.graph` (types, cardinalites, dedup)
