# Viz Agent Python

README global du projet Data Viz PFE (conversion Tableau -> RDL, validation, lineage, benchmark LLM).

## 1. Vision et objectifs

Viz Agent transforme des fichiers Tableau (`.twb` / `.twbx`) en livrables exploitables pour SSRS/Report Builder et pour l'audit BI.

Objectifs principaux:
1. Convertir un dashboard Tableau vers un rapport RDL executable.
2. Produire des artefacts intermediaires pour comprendre le pipeline.
3. Fiabiliser la generation via validation multi-niveaux + auto-fix.
4. Exposer un mode agentique avec detection d'intention utilisateur FR/EN.

Livrables principaux d'un run:
1. RDL final (`.rdl`).
2. Semantic model (`*_semantic_model.json`).
3. Abstract spec (`*_abstract_spec.json`).
4. Visualisation HTML de la spec (`*_abstract_spec_visualization.html`).
5. Lineage (`*_lineage.json`).
6. Trace d'execution par phase (`*_phase_trace.jsonl`, `*_phase_results.json`, `*_pipeline_summary.json`).
7. Exports bruts phase 0 (`*_raw_select_star/`).

Point d'entree runtime:
1. Script wrapper: `main.py`.
2. Orchestrateur principal: `viz_agent/main.py`.

## 2. Architecture globale

Le pipeline est organise en 7 phases (+ validation 3b):

| Phase | Nom | Role |
|---|---|---|
| 0 | Extraction | Detection des sources, extraction Hyper/CSV, connexions live |
| 1 | Parser | Construction du `ParsedWorkbook` |
| 2 | Semantic | Enrichissement semantique hybride + lineage logique |
| 3 | Spec | Construction de l'Abstract Spec |
| 3b | Validation Spec | Controle de qualite et blocage si critique |
| 4 | Transform | Preparation du tool model cible |
| 5 | RDL | Generation RDL + validation/auto-fix |
| 6 | Lineage export | Export lineage final pour audit |

Documentation locale par phase:
1. `viz_agent/phase0_extraction/README.md`
2. `viz_agent/phase1_parser/README.md`
3. `viz_agent/phase2_semantic/README.md`
4. `viz_agent/phase3_spec/README.md`
5. `viz_agent/phase3b_validator/README.md`
6. `viz_agent/phase4_transform/README.md`
7. `viz_agent/phase5_rdl/README.md`
8. `viz_agent/phase6_lineage/README.md`

## 3. Prerequis et installation

Prerequis:
1. Python 3.11+ (3.14 compatible dans ce workspace).
2. Acces reseau si vous utilisez les APIs LLM externes.

Installation:

```bash
pip install -r requirements.txt
```

Cles LLM (au moins une):
1. `MISTRAL_API_KEY`
2. `GEMINI_API_KEY`

Note:
1. Le runtime charge egalement les cles via `API_KEY.txt` (fallback).

## 4. Demarrage rapide

Depuis le dossier `Data_viz_pfe-version-py`.

### 4.1 Conversion standard

```bash
python main.py --input input/demo_csv.twbx --output output/demo_csv.rdl
```

Formats d'entree supportes:
1. `.twb`
2. `.twbx`

### 4.2 Avec contraintes d'intention

```bash
python main.py \
  --input input/demo_ssms.twbx \
  --output output/demo_ssms.rdl \
  --intent-type conversion \
  --intent-constraints "{\"strict_mode\": false, \"force_numeric_y\": true}"
```

Valeurs acceptees pour `--intent-type`:
1. `conversion`
2. `generation`
3. `analysis`
4. `optimization`

### 4.3 Detection d'intention FR/EN (nouveau)

Vous pouvez decrire votre besoin en langage naturel.

```bash
python main.py \
  --input input/demo_ssms.twbx \
  --output output/demo_ssms.rdl \
  --user-request "Convertir ce dashboard sans modification en RDL"
```

Exemple avec modifications:

```bash
python main.py \
  --input input/demo_ssms.twbx \
  --output output/demo_ssms.rdl \
  --user-request "Convert this BI report with modifications: add country filter and change bar chart to line chart in PDF"
```

Intents pris en charge par l'agent:
1. Conversion sans modification + format de sortie.
2. Conversion avec modifications + liste de changements + format de sortie.
3. Creation depuis zero + specs de charts.

## 5. CLI reference

Options principales (`python main.py --help`):
1. `--input`: chemin du `.twb`/`.twbx` source.
2. `--output`: chemin de sortie (souvent `.rdl`).
3. `--user-request`: demande utilisateur FR/EN pour detection agentique.
4. `--intent-type`: override manuel du type d'intention.
5. `--intent-constraints`: JSON de contraintes supplementaires.
6. `--no-report-filters`: desactive la propagation des filtres globaux vers les ReportParameters RDL.

## 6. Module de detection d'intention (FR/EN)

Composant:
1. `viz_agent/orchestrator/user_intent_detection_agent.py`

Comportement:
1. Classification FR/EN de l'intention utilisateur.
2. Extraction du format cible (rdl/pdf/html/json/...)
3. Extraction des modifications demandees.
4. Extraction de chart specs (bar, line, pie, kpi, treemap, etc.).
5. Production d'un payload structure dans `intent_detection`:
   - `agent`
   - `supervised_by`
   - `confidence`
   - `language`
   - `request`
   - `modifications`
   - `chart_specs`
   - `agentic`

Integration pipeline:
1. Construction d'intention centralisee dans `viz_agent/main.py`.
2. Intent injecte des la phase 2 (semantic orchestrator).

## 7. Artefacts generes

Pour une sortie `X.rdl`, vous obtenez typiquement:
1. `X.rdl`
2. `X_lineage.json`
3. `X_semantic_model.json`
4. `X_abstract_spec.json`
5. `X_abstract_spec_visualization.html`
6. `X_tool_model.json`
7. `X_phase0_connections.json`
8. `X_phase0_manifest.json`
9. `X_phase1_parsed_workbook.json`
10. `X_phase_results.json`
11. `X_pipeline_summary.json`
12. `X_phase_trace.jsonl`
13. dossier `X_raw_select_star/`

## 8. Details par phase (resume operationnel)

### Phase 0 - Extraction

Fait:
1. Detection format entree.
2. Extraction Hyper/CSV pour `.twbx`.
3. Detection connexions live.
4. Construction du `DataSourceRegistry`.
5. Emission du manifest (`extract`, `live_sql`, `hybrid`, `xml_only`).

### Phase 1 - Parser

Fait:
1. Parsing workbook Tableau.
2. Extraction dashboards, worksheets, datasources, calculs, filtres.
3. Mapping encodages visuels (`x`, `y`, `color`, `size`, `detail`).
4. Production snapshot JSON du parsed workbook.

### Phase 2 - Semantic hybride

Fait:
1. Mapping schema + joins.
2. Enrichissement semantique heuristique/LLM.
3. Construction `SemanticModel` + `DataLineageSpec`.
4. Prise en compte de l'intention structuree.

### Phase 3 + 3b - Abstract Spec + validation

Fait:
1. Construction des `DataBinding` par visual.
2. Decision du type visuel.
3. Validation et scoring.
4. Blocage en cas d'erreurs critiques.

### Phase 4 - Transformation

Fait:
1. Traduction des calculs vers expressions cibles.
2. Construction du tool model RDL-friendly.
3. Validation des sorties de transformation.

### Phase 5 - RDL generation + validation

Fait:
1. Generation RDL.
2. Validation XML, structure, semantique.
3. Auto-fix deterministe.
4. Revalidation avant ecriture finale.

Stabilisations recentes:
1. Protection des noms internes de charts (evite renaming destructif).
2. Unicite globale des noms de groupes (`Group/@Name`).
3. Selection Y plus robuste (evite aggregation de dimensions textuelles).

### Phase 6 - Lineage

Fait:
1. Export final du lineage pour audit.

## 9. Execution demo complete

Script:
1. `main_demo.py`

Exemple:

```bash
python main_demo.py --output-dir output/demo_complete
```

Exemple mode planner modulaire (avec runtime validation):

```bash
python main_demo.py --output-dir output/demo_complete --modular-agentic
```

Sorties habituelles:
1. RDL final de demo.
2. Dashboard HTML de synthese.
3. Ensemble des artefacts de phase.

## 10. Tests

Suite globale:

```bash
python -m pytest tests -q
```

Suites utiles:

```bash
python -m pytest tests/test_rdl_validator_pipeline.py -q
python -m pytest viz_agent/tests/test_phase5_rdl.py -q
python -m pytest viz_agent/tests/test_user_intent_detection_agent.py -q
python -m pytest viz_agent/tests/test_main.py -q
python -m pytest viz_agent/tests/test_validation_hooks.py -q
python -m pytest viz_agent/tests/test_lineage_hooks.py -q
python -m pytest viz_agent/tests/test_orchestrator_self_healing.py -q
```

## 11. Benchmark comparatif LLM

Dossier dedie:
1. `benchmark/`

Contenu:
1. `benchmark/scenarios.json`: scenarios d'evaluation.
2. `benchmark/run_benchmark.py`: runner benchmark.
3. `benchmark/README.md`: mode d'emploi benchmark.

Usage de base:

```bash
python benchmark/run_benchmark.py --mode simulate
```

Note:
1. Le benchmark supporte des profils differencies (mistral_api, gemini_api, mistral_local) et genere un leaderboard JSON/Markdown.

## 12. Arborescence utile

1. `main.py`: wrapper d'entree.
2. `viz_agent/main.py`: orchestration pipeline.
3. `viz_agent/orchestrator/`: agents, factory, supervision.
4. `viz_agent/models/`: schemas de donnees.
5. `viz_agent/phase*/`: implementation par phase.
6. `viz_agent/validators/`: validation transversale.
7. `tests/` et `viz_agent/tests/`: tests unitaires et integration.
8. `input/`: fichiers de demo.
9. `output/`: artefacts generes.

## 13. Troubleshooting

Probleme: aucune cle API detectee.
1. Verifier `MISTRAL_API_KEY` et/ou `GEMINI_API_KEY`.
2. Verifier le contenu de `API_KEY.txt`.

Probleme: RDL genere mais affichage vide.
1. Verifier dans `*_abstract_spec.json` et `*_tool_model.json` que les champs Y sont numeriques.
2. Verifier la presence des fields attendus dans les datasets.

Probleme: erreur schema/nom duplicate en SSRS.
1. Verifier `*_phase_results.json` et les warnings phase 5.
2. Regenerer apres correction du mapping source.

Probleme: sortie incoherente entre design/execution.
1. Comparer `*_phase1_parsed_workbook.json` et `*_semantic_model.json`.
2. Verifier les alias SQL et les mesures resolues dans le RDL.

## 14. Limites connues

1. Certains cas tres specifiques de visuals Tableau vers SSRS peuvent tomber en fallback.
2. La qualite semantique depend de la qualite des metadata source.
3. Les performances varient selon taille workbook, disponibilite extracts et enrichissement LLM.

## 15. Roadmap courte

1. Renforcer les mappings de visuals complexes SSRS.
2. Etendre la supervision agentique a davantage d'etapes.
3. Ajouter plus de jeux de tests de non-regression orientes execution SSRS.

## 16. Runbook operationnel

Le runbook complet (execution, diagnostics, reprise incident, checklists) est disponible ici:
1. `RUNBOOK_OPERATIONNEL.md`
