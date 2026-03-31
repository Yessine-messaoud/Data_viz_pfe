# Viz Agent Python

## 1) Objectif du projet

Ce module convertit un workbook Tableau (`.twbx`) en artefacts exploitables pour le reporting pagine et la tracabilite des donnees:

- un rapport RDL (SSRS / Report Builder)
- un lineage JSON
- un Abstract Spec JSON
- une visualisation HTML de l Abstract Spec
- un export brut des tables extraites (CSV + HTML index)

Le pipeline est orchestre par [version_py/viz_agent/main.py](version_py/viz_agent/main.py).

## 2) Ce que fait exactement le pipeline

Pipeline reel execute en 7 phases (0 a 6):

1. Phase 0 - Data source extraction
- Extrait les donnees Hyper et CSV depuis le `.twbx`
- Construit un registre de sources (`DataSourceRegistry`)
- Genere un dossier `*_raw_select_star` avec un `index.html` et des CSV/HTML table par table

2. Phase 1 - Tableau parsing
- Parse le workbook (worksheets, dashboards, calculs)

3. Phase 2 - Hybrid semantic layer
- Construit le modele semantique enrichi (LLM Mistral + logique locale)
- Produit les objets de lineage

4. Phase 3 - AbstractSpec build + validation
- Construit l Abstract Spec
- Valide l Abstract Spec (score + blocage si invalide)
- Ecrit:
	- `*_abstract_spec.json`
	- `*_abstract_spec_visualization.html`

5. Phase 4 - Calc field translation
- Traduit les champs calcules vers des expressions RDL

6. Phase 5 - RDL generation + validation
- Genere le RDL depuis le spec, les datasets et les layouts
- Valide le RDL en 3 niveaux (phase 5.1):
	- XML (syntaxe, namespace)
	- Schema (structure RDL)
	- Semantique (references datasets/champs/parametres)
- Applique des auto-fix deterministes (max 3 tours)
- Bloque l ecriture du fichier `.rdl` si erreurs persistantes

7. Phase 6 - Lineage export
- Ecrit `*_lineage.json`

## 3) Workflow recommande (de A a Z)

1. Ouvrir un terminal dans [version_py](version_py).
2. Installer les dependances Python.
3. Configurer l acces Mistral (`MISTRAL_API_KEY`).
4. Lancer la conversion avec `--input` et `--output`.
5. Verifier les artefacts dans `output/`.
6. Ouvrir le RDL dans Report Builder.

Commande type:

```powershell
c:/python312/python.exe main.py --input "C:/Users/User/OneDrive/Desktop/TALAN/PFE/Coeur/Input/Ventes par Pays.twbx" --output "C:/Users/User/OneDrive/Desktop/TALAN/PFE/Coeur/version_py/output/vente_par_pays_v19.rdl"
```

## 4) Prerequis et outils utilises

Prerequis runtime:

- Python 3.11+
- SQL Server accessible (exemple local: `localhost\SQLEXPRESS`)
- Base cible (par defaut: `AdventureWorksDW2022`)
- Report Builder/SSRS pour ouvrir le RDL

Dependances Python (voir [version_py/viz_agent/requirements.txt](version_py/viz_agent/requirements.txt)):

- `pydantic` (modeles)
- `lxml` (generation/validation XML RDL)
- `mistralai` (appel LLM)
- `aiohttp` (HTTP async)
- `pandas` (manipulation tabulaire)
- `sqlalchemy` (utilitaires SQL)
- `pantab` / `tableauhyperapi` (lecture Hyper)
- `pytest`, `pytest-asyncio` (tests)

## 5) Configuration

Variables d environnement:

- `MISTRAL_API_KEY` (obligatoire)
- `MISTRAL_MODEL` (defaut: `mistral-small-latest`)
- `MISTRAL_BASE_URL` (defaut: `https://api.mistral.ai/v1`)
- `VIZ_AGENT_RDL_CONNECTION_STRING` (connexion SQL du rapport)
- `VIZ_AGENT_ONTOLOGY_PATH` (optionnel, chemin JSON ontologie metier)
- `VIZ_AGENT_SEMANTIC_GRAPH_ENABLED` (optionnel, active export Neo4j)
- `VIZ_AGENT_NEO4J_URI` (defaut: `bolt://localhost:7687`)
- `VIZ_AGENT_NEO4J_USER` (defaut: `neo4j`)
- `VIZ_AGENT_NEO4J_PASSWORD` (obligatoire si graphe active)

Connexion RDL par defaut:

```text
Data Source=localhost\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022
```

Exemple PowerShell:

```powershell
$env:VIZ_AGENT_RDL_CONNECTION_STRING = "Data Source=localhost\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022"
```

Comportement actuel cote RDL:

- `IntegratedSecurity=true` (authentification Windows)
- Les cles sensibles (`User ID`, `Password`, etc.) sont retirees de la connection string

## 6) Details techniques importants du projet

Organisation principale du code:

- [version_py/viz_agent/phase0_data](version_py/viz_agent/phase0_data): extraction Hyper/CSV
- [version_py/viz_agent/phase1_parser](version_py/viz_agent/phase1_parser): parsing Tableau
- [version_py/viz_agent/phase2_semantic](version_py/viz_agent/phase2_semantic): enrichissement semantique
- [version_py/viz_agent/phase3_spec](version_py/viz_agent/phase3_spec): construction Abstract Spec
- [version_py/viz_agent/phase3b_validator](version_py/viz_agent/phase3b_validator): validation Abstract Spec
- [version_py/viz_agent/phase4_transform](version_py/viz_agent/phase4_transform): transformation calculs/datasets
- [version_py/viz_agent/phase5_rdl](version_py/viz_agent/phase5_rdl): generation layout/RDL + validation 3 niveaux
- [version_py/viz_agent/phase6_lineage](version_py/viz_agent/phase6_lineage): export lineage

Points d implementation recents:

- Generation chart en mode deterministe pour eviter les structures XML invalides en Report Builder
- Normalisation stricte des hierarchies de chart (`ChartMembers`)
- Correction de query placeholder Tableau `('Extract','Extract')` vers SQL Server valide
- Validation RDL avant ecriture disque avec auto-fix et blocage en cas d erreur

## 7) Artefacts de sortie

Pour une sortie `X.rdl`, le pipeline produit:

- `X.rdl`
- `X_lineage.json`
- `X_semantic_model.json`
- `X_abstract_spec.json`
- `X_abstract_spec_visualization.html`
- dossier `X_raw_select_star/` (index + CSV/HTML des tables extraites)

Le fichier `X_semantic_model.json` contient:

- `semantic_model`: modele semantique consolide (mesures, dimensions, fact table)
- `phase2_artifacts.ontology`: ontologie chargee (base + override)
- `phase2_artifacts.mappings`: mapping colonnes -> termes metier
- `phase2_artifacts.graph`: noeuds/relations graph et statut de persistence Neo4j

Exemple ouverture visualisation:

```powershell
start .\output\vente_par_pays_v19_abstract_spec_visualization.html
```

## 8) Tests

Lancer les tests:

```powershell
python -m pytest tests -q
```

Config pytest: [version_py/pytest.ini](version_py/pytest.ini)

## 9) Erreurs frequentes et resolution

1. `Input file not found`
- Verifier le chemin `--input`.

2. `Input must be a .twbx file`
- Utiliser un fichier Tableau package `.twbx`.

3. `Invalid object name 'Extract.Extract'`
- Le placeholder Tableau ne correspond pas a une table SQL reelle.
- Utiliser la derniere generation qui mappe ce cas vers une requete AdventureWorksDW valide.

4. Erreurs de deserialisation chart dans Report Builder
- Utiliser les versions recentes du generateur (charts schema-safe + validation phase 5.1).

5. Erreurs d authentification SQL
- Verifier le compte Windows et les droits SQL Server.
- Verifier `VIZ_AGENT_RDL_CONNECTION_STRING`.

## 10) Documentation complementaire

- Guide local detaille: [version_py/README_LOCAL_RUN.md](version_py/README_LOCAL_RUN.md)
- Documentation phase 2 semantique: [version_py/README_PHASE2.md](version_py/README_PHASE2.md)
- Exemple dataset: [version_py/examples/dataset_usage_example.md](version_py/examples/dataset_usage_example.md)
