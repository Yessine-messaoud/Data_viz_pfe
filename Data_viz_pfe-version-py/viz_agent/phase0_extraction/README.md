
# Phase 0 — Extraction universelle des métadonnées (VizAgent)

## Objectif
Extraire toutes les métadonnées (tables, colonnes, relations) d'une source BI (Tableau ou RDL), y compris les éléments non utilisés dans les dashboards, pour permettre un export RDL enrichi et un catalogue drag & drop.

## Fonctionnalités principales
- **Détection automatique du mode** : Tableau Extract (.hyper), Tableau Live (SQL Server), RDL Live (SQL Server)
- **Extraction brute** : tables, colonnes, types, schémas, row_count, etc.
- **Identification des colonnes utilisées** dans les visuels (is_used_in_dashboard)
- **Normalisation** : transformation en modèle universel Pydantic strict
- **Profiling optionnel** : distinct_count, null_ratio (échantillon max 1000 lignes)
- **Détection des relations** : Foreign Keys SQL + heuristiques (suffixes ID/Key)
- **Catalogue** : accès aux colonnes disponibles pour le drag & drop
- **Export** : JSON et YAML du modèle de métadonnées
- **Pipeline orchestrateur** : workflow complet avec cache fichier intelligent

## Structure des modules
```
phase0_extraction/
├── adapters/                # Détection et extraction (Tableau, RDL)
├── readers/                 # Lecture Hyper/SQL/CSV
├── normalization/           # Normalisation → MetadataModel
├── enrichment/              # Profiling colonnes
├── relationship_detection/  # Détection relations
├── registry/                # Catalogue
├── export/                  # Export JSON/YAML
├── pipeline.py              # Orchestrateur principal
├── models.py                # Modèle Pydantic universel
└── tests/                   # Tests unitaires
```

## Modèle de données universel
- Voir `models.py` pour la structure complète (Column, Table, Relationship, MetadataModel)
- Champs clés : `is_used_in_dashboard`, `role`, `distinct_count`, `null_ratio`, `extraction_warnings`

## Usage rapide
```python
from viz_agent.phase0_extraction.pipeline import MetadataExtractor
extractor = MetadataExtractor()
model = extractor.extract("/path/to/source.twbx", enable_profiling=True)
model.tables  # Liste des tables et colonnes
```

## Tests
- Tous les modules sont couverts par des tests unitaires (voir dossier `tests/`)
- Lancer tous les tests :
    ```powershell
    powershell -ExecutionPolicy Bypass -File run_all_tests.ps1
    ```

## Spécifications détaillées
- Voir le prompt complet dans `Prompts/prompt_metadata_extraction_v2.md`
- Respect strict du modèle et des signatures
- Gestion des erreurs robuste (warnings, jamais d'exception non catchée)
