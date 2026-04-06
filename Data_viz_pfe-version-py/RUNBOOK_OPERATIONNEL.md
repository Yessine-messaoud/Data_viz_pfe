# Runbook Operationnel Viz Agent

Ce document fournit un mode operatoire complet pour executer, diagnostiquer et maintenir le pipeline Viz Agent (Tableau -> RDL) en environnement dev, recette et production.

## 1. Objectif et perimetre

Ce runbook couvre:
1. Modes d execution (pipeline standard et agentique).
2. Preconditions techniques et variables d environnement.
3. Artefacts attendus et points de controle.
4. Diagnostics par symptome.
5. Strategie de reprise incident.
6. Checklists de validation operationnelle.

## 2. Prerequis

## 2.1 Runtime

1. Python 3.11+ (3.14 valide dans ce projet).
2. Dependances installees:

```bash
pip install -r requirements.txt
```

## 2.2 Cles LLM

Au moins un provider doit etre disponible pour les etapes LLM:
1. `MISTRAL_API_KEY`
2. `GEMINI_API_KEY`

Fallback possible via fichier `API_KEY.txt` (charge automatiquement).

## 2.3 Variables utiles

1. `VIZ_AGENT_API_KEY_FILE`: chemin explicite vers fichier de cles.
2. `VIZ_AGENT_ENABLE_LLM_FALLBACK`: active corrections LLM (`true`/`false`).
3. `VIZ_AGENT_ENABLE_LLM_SELF_EVAL`: active self-eval LLM phase3/phase5.
4. `VIZ_AGENT_RDL_CONNECTION_STRING`: connection string cible pour datasource RDL.
5. `VIZ_AGENT_DISABLE_REPORT_FILTERS`: desactive propagation filtres vers RDL.

## 3. Modes d execution

## 3.1 Pipeline standard (recommande)

Commande:

```bash
python main.py --input input/demo_ssms.twbx --output output/demo_ssms.rdl
```

Usage:
1. Conversion complete phase0 -> phase6.
2. Generation de tous les artefacts de controle.
3. Mode principal pour build de livrable.

## 3.2 Pipeline standard avec intention explicite

```bash
python main.py \
  --input input/demo_ssms.twbx \
  --output output/demo_ssms.rdl \
  --intent-type conversion \
  --intent-constraints "{\"strict_mode\": false}"
```

## 3.3 Detection d intention FR/EN

```bash
python main.py \
  --input input/demo_ssms.twbx \
  --output output/demo_ssms.rdl \
  --user-request "Convert this BI report with modifications: add country filter and change chart type to line"
```

## 3.4 Mode agentique tools only (debug orchestration)

```bash
python main.py \
  --input input/demo_ssms.twbx \
  --output output/demo_ssms.rdl \
  --agentic-conversion-only
```

Usage:
1. Validation de la boucle agentique phase0 -> phase5.
2. Verification retries, fallback et cache.

## 3.5 Mode planner modulaire Sprint 3

```bash
python main.py \
   --input input/demo_ssms.twbx \
   --output output/demo_ssms.rdl \
   --modular-agentic-conversion-only
```

Usage:
1. Execution via planner modulaire (Parsing -> Semantic -> Specification -> Transformation -> Export -> Validation).
2. Retry par agent avec priorite fallback deterministic -> heuristic -> llm.
3. Traces et snapshots compatibles contrat agentique.

Artefacts dedies:
1. `*_modular_agentic_results.json`
2. `*_modular_agentic_phase_trace.jsonl`
3. `*_modular_agentic_snapshots/`

## 4. Artefacts de sortie attendus

Pour une sortie `X.rdl`, verifier:
1. `X.rdl`
2. `X_semantic_model.json`
3. `X_abstract_spec.json`
4. `X_abstract_spec_visualization.html`
5. `X_tool_model.json`
6. `X_lineage.json`
7. `X_phase0_manifest.json`
8. `X_phase0_connections.json`
9. `X_phase1_parsed_workbook.json`
10. `X_phase_results.json`
11. `X_pipeline_summary.json`
12. `X_phase_trace.jsonl`
13. `X_agentic_snapshots/` (si snapshots actifs)
14. `X_raw_select_star/`

En mode agentique conversion only:
1. `X_agentic_results.json`
2. `X_agentic_phase_trace.jsonl`
3. `X_agentic_snapshots/`

## 5. Observabilite et diagnostics

## 5.1 Lecture rapide des traces

1. Ouvrir `*_phase_trace.jsonl` pour timeline phase-by-phase.
2. Rechercher les evenements:
   - `validation_gate_failed`
   - `deterministic_fix`
   - `heuristic_fix`
   - `llm_fix`
   - `llm_self_eval`
   - `runtime_validation_started`
   - `runtime_validation_success`
   - `runtime_validation_failed`
   - `runtime_error_detected`
   - `cache_hit`
   - `cache_write`
3. Correlier avec `*_phase_results.json` (score/confiance/erreurs).

## 5.2 Interpretation des scores

1. `confidence > 0.8`: acceptance normale.
2. `0.5 < confidence < 0.8`: retry correctif (deterministic/heuristic).
3. `confidence < 0.5`: fallback agressif (incluant LLM si actif).
4. Self-eval:
   - phase3 seuil par defaut: 0.70
   - phase5 seuil par defaut: 0.75

## 5.3 Verification du cache

1. Dossier cache par defaut:
   - si trace connue: `<trace_dir>/.viz_agent_cache`
   - sinon: `.viz_agent_cache` a la racine d execution
2. Fichiers:
   - `.viz_agent_cache/phases/*.json`
   - `.viz_agent_cache/artifacts/*.json`
3. Indicateurs runtime:
   - presence de `cache_hit` dans la trace
   - baisse du nombre d appels phase/agent sur rerun identique

## 6. Strategie de reprise incident

## 6.1 Niveaux de severite

1. P1: pipeline bloque, pas de RDL livrable.
2. P2: RDL genere mais incomplet/incoherent.
3. P3: warning non bloquant, qualite degradee.

## 6.2 Procedure standard de reprise

1. Capturer contexte:
   - input exact
   - commande exacte
   - hash commit
   - fichiers `*_phase_trace.jsonl`, `*_phase_results.json`, `*_pipeline_summary.json`
2. Identifier phase en erreur depuis `phase_results`.
3. Rejouer en mode cible:
   - standard si besoin livrable
   - `--agentic-conversion-only` si debug orchestration
4. Activer fallback LLM seulement si necessaire:
   - `VIZ_AGENT_ENABLE_LLM_FALLBACK=true`
5. Rejouer et comparer traces (avant/apres).
6. Si echec persistant, ouvrir incident avec lot d evidences.

## 6.3 Playbook par symptome

### A. RDL genere mais affichage vide

Checks:
1. Dans `*_tool_model.json`, verifier bindings Y et datasets.
2. Dans `*_abstract_spec.json`, verifier axes pour visuels chart.
3. Dans trace, verifier `validation_gate_failed` phase3/phase5.

Actions:
1. Verifier qu aucune aggregation sur dimension n existe.
2. Forcer rerun avec self-eval active.
3. Controler `DataSet/Filters` si filtres trop restrictifs.

### B. Erreur schema/datasource SSRS

Checks:
1. `rdl_schema_validator` issues (S00x).
2. `DataSources/DataSource/ConnectionProperties/ConnectString` non vide.
3. `DataSet/Query/DataSourceName` coherent.

Actions:
1. Ajuster `VIZ_AGENT_RDL_CONNECTION_STRING`.
2. Rejouer pipeline et verifier `cache_write`/`cache_hit`.

### C. Regressions de mapping visuel

Checks:
1. Type visuel final != `chart` generique.
2. Axe `size` ne reference pas de dimension.
3. Presence de warnings `visual_mapping` et `visual_correction`.

Actions:
1. Rejouer avec traces et snapshots.
2. Executer suite regression (section 8).

### D. Joins incoherents

Checks:
1. `DataLineageSpec.joins` dans `*_semantic_model.json`.
2. Presence de joins `inferred_from_columns` si pas de relationships source.

Actions:
1. Verifier colonnes `*_id` / `*_key` dans les datasources.
2. Rejouer phase2/standard run.

## 6.4 Politique d echec planner modulaire

Politique:
1. Echec de gate deterministe: retry tant que `attempt <= max_retries`.
2. A chaque retry: appliquer deterministic puis heuristic; llm uniquement a partir de la tentative 2.
3. Self-eval phase3/phase5 sous seuil: phase marquee en erreur et re-tentee.
4. Si `stop_on_error=true`, abort immediat au premier agent en echec final.
5. Validation globale finale executee meme en cas d echec intermediaire pour produire un diagnostic complet.
6. Runtime validation en echec: routage correctif par type d erreur:
   - `schema_error` -> `export` (RDLAgent)
   - `datasource_error` -> `semantic_reasoning` (SemanticAgent)
   - `rendering_error` -> `specification` (VisualizationAgent)

Codes de sortie pratiques:
1. `status=success`: toutes phases + validation OK.
2. `status=failed`: au moins un agent ou une gate en echec final.
3. Consulter `errors[]` dans `*_modular_agentic_results.json` pour action corrective.

## 6.5 Exemple de boucle d erreur runtime

Flux:
1. `export` genere `*.rdl`.
2. `runtime_validation` tente ouverture locale + parse XML + checks SSRS locaux.
3. Erreur detectee (ex: `Element 'Textbox' is invalid`) normalisee en:
   - `type=schema_error`, `location=Textbox`, `severity=P1`.
4. Planner emet `runtime_error_detected`, relance `export`, puis retente `runtime_validation`.
5. Si succes: pipeline continue vers `validation`.
6. Si echec final apres retries: statut global `failed` avec erreurs structurees.

## 7. Checklists de validation

## 7.1 Checklist pre-run

1. Input `.twb`/`.twbx` present et lisible.
2. `requirements.txt` installe.
3. Cle API valide si LLM requis.
4. Dossier output accessible en ecriture.
5. Variables d env controlees (`VIZ_AGENT_*`).

## 7.2 Checklist post-run (fonctionnel)

1. `*.rdl` genere.
2. `*_phase_results.json` sans erreurs bloquantes.
3. `*_lineage.json` genere.
4. `*_tool_model.json` sans `validation_results` severity error.
5. Filtres globaux correctement propages (si presents).

## 7.3 Checklist post-run (qualite)

1. Pas de mesure invalide (aggregation dimensionnelle).
2. Pas de `chart` generique non normalise.
3. Pas de dimension sur axe `size`.
4. Joins semantiques coherents.
5. Datasource metadata presente dans RDL.

## 8. Commandes de verification recommandees

## 8.1 Tests coeur agentique

```bash
python -m pytest viz_agent/tests/test_validation_gates.py -q
python -m pytest viz_agent/tests/test_agentic_loop_integration.py -q
```

## 8.2 Tests regression pipeline

```bash
python -m pytest viz_agent/tests/test_pipeline_regression_fixes.py -q
python -m pytest viz_agent/tests/test_phase2.py -q
python -m pytest viz_agent/tests/test_phase5_rdl.py -q
python -m pytest viz_agent/tests/test_phase_tool_agents.py -q
```

## 8.3 Suite cible complete (hors live externes)

```bash
python -m pytest viz_agent/tests -q -k "not mistral_integration"
```

## 9. Maintenance operationnelle

## 9.1 Hygiene cache

1. Purger `.viz_agent_cache` en cas de changement structurel majeur.
2. Garder cache actif en routine pour reduire latence/cout.

## 9.2 Politique de rerun

1. Rerun identique attendu plus rapide (cache hit).
2. En cas de comportements non deterministes, invalider cache et relancer.

## 9.3 Escalade

Escalader vers equipe dev si:
1. 2 reruns consecutifs echouent sur meme input.
2. self-eval reste sous seuil malgre fallback.
3. RDL passe les validateurs mais echoue au runtime SSRS sans signal interne.

## 10. Template de ticket incident

Copier-coller ce bloc:

```text
Titre: [P1|P2|P3] VizAgent pipeline incident - <date>
Input: <path fichier>
Commande: <commande complete>
Commit: <hash>
Env: <variables VIZ_AGENT_*>
Symptome: <description>
Phase en echec: <phase>
Dernier retry hint: <hint>
Artifacts joints:
- *_phase_trace.jsonl
- *_phase_results.json
- *_pipeline_summary.json
- *_tool_model.json
- *_semantic_model.json
Hypothese: <cause probable>
Actions deja tentees: <liste>
```

## 11. Definition of done operationnelle

Un run est considere acceptable production si:
1. RDL genere et valide.
2. Aucune erreur bloquante dans `phase_results`.
3. Self-eval phase3/phase5 au dessus des seuils (si active).
4. Checklists 7.2 et 7.3 valides.
5. Tests regression critiques au vert.
