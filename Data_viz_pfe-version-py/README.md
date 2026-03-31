# Viz Agent Python

## Presentation

Ce projet convertit des artefacts Tableau (`.twb` / `.twbx`) en artefacts exploitables pour le reporting pagine et la tracabilite:

- Rapport RDL (SSRS / Report Builder)
- Lineage JSON
- Abstract Spec JSON
- Visualisation HTML de l'Abstract Spec
- Export brut des tables extraites (CSV + HTML index)

Le pipeline est execute par `viz_agent/main.py` et s'appuie sur 7 phases modulaires:

| Phase | Description | Documentation |
|---|---|---|
| 0 | Extraction des metadonnees et sources | `viz_agent/phase0_extraction/README.md` |
| 1 | Parsing Tableau | `viz_agent/phase1_parser/README.md` |
| 2 | Hybrid semantic layer | `viz_agent/phase2_semantic/README.md` |
| 3 | Construction Abstract Spec | `viz_agent/phase3_spec/README.md` |
| 3b | Validation Abstract Spec | `viz_agent/phase3b_validator/README.md` |
| 4 | Transformation / calculs / mapping | `viz_agent/phase4_transform/README.md` |
| 5 | Generation + validation RDL | `viz_agent/phase5_rdl/README.md` |
| 6 | Export lineage | `viz_agent/phase6_lineage/README.md` |

## Prerequis

- Python 3.11+
- Dependances Python:
  - installer via `pip install -r requirements.txt`
- Cle API Mistral:
  - variable `MISTRAL_API_KEY` requise pour les etapes LLM

## Installation

```bash
pip install -r requirements.txt
```

## Execution

Exemple standard:

```bash
python main.py --input input/demo_csv.twbx --output output/demo.rdl
```

Support entree:

- `.twbx`
- `.twb`

Options intent (ajoutees recemment):

- `--intent-type` : `conversion|generation|analysis|optimization`
- `--intent-constraints` : JSON (ex: `{"strict_mode": true}`)

Exemple:

```bash
python main.py --input input/demo.twb --output output/demo.rdl --intent-type conversion --intent-constraints "{\"strict_mode\": false}"
```

## Artefacts produits

Pour une sortie `X.rdl`:

- `X.rdl`
- `X_lineage.json`
- `X_semantic_model.json`
- `X_abstract_spec.json`
- `X_abstract_spec_visualization.html`
- dossier `X_raw_select_star/`

## Etat actuel (coherence pipeline)

Mises a jour recentes integrees:

- compatibilite `phase0_data` restauree (migration vers `phase0_extraction` en cours)
- intent structure dynamique dans `main.py`
- support `.twb` ajoute dans le runtime et dans le parser Tableau
- hooks de validation continue actifs (phases 1, 2, 4)
- hooks lineage continu actifs (phases 1, 2, 4)
- self-healing partiel operationnel dans l'orchestrateur agentique

## Tests

Lancer les tests:

```bash
python -m pytest tests -q
```

Tests cibles utilises pendant la stabilisation:

```bash
python -m pytest viz_agent/tests/test_main.py -q
python -m pytest viz_agent/tests/test_validation_hooks.py -q
python -m pytest viz_agent/tests/test_lineage_hooks.py -q
python -m pytest viz_agent/tests/test_orchestrator_self_healing.py -q
```
