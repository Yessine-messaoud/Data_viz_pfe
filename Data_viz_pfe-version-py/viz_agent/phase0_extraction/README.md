
# Phase 0 — Extraction universelle des métadonnées (VizAgent)

## Objectif
La phase 0 transforme une source BI Tableau ou RDL en un inventaire de métadonnées stable, normalisé et exploitable par les phases suivantes.

Cette phase doit:
- détecter le type de source et son mode d'accès,
- extraire les structures de données disponibles,
- identifier ce qui est utilisé dans les dashboards,
- enrichir les métadonnées par profiling et détection de relations,
- produire un modèle Pydantic universel,
- alimenter le catalogue de colonnes et l'export final.

## Fonctionnalités principales
- **Détection automatique du mode** : Tableau Extract (.hyper), Tableau Live (SQL Server), RDL Live (SQL Server)
- **Extraction brute** : tables, colonnes, types, schémas, row_count, connexions, vues et champs calculés
- **Identification des colonnes utilisées** dans les visuels (`is_used_in_dashboard`)
- **Normalisation** : transformation en modèle universel Pydantic strict
- **Profiling optionnel** : `distinct_count`, `null_ratio`, valeurs fréquentes, échantillon limité
- **Détection des relations** : foreign keys SQL + heuristiques (suffixes `ID`, `Key`, colonnes de jointure)
- **Catalogue** : accès aux colonnes disponibles pour le drag & drop
- **Export** : JSON et YAML du modèle de métadonnées
- **Pipeline orchestrateur** : workflow complet avec cache fichier intelligent

## Déroulé détaillé

### 1. Détection du format et du mode d'entrée
Sous-étapes:
- lire l’extension du fichier source (`.twb`, `.twbx`, RDL, etc.),
- choisir l’adaptateur compatible,
- déterminer le mode d’extraction: extract, live, ou hybride,
- préparer le contexte d’exécution et la registry vide.

Résultat attendu:
- un mode d’extraction explicite,
- une structure d’exécution prête pour les étapes suivantes,
- des warnings si le format est partiellement supporté.

### 2. Extraction des sources de données
Sous-étapes:
- détecter les connexions contenues dans le fichier source,
- extraire les tables embarquées ou accessibles en live,
- récupérer les colonnes physiques et leurs types,
- capturer les schémas, tables, row counts et métadonnées de base,
- isoler les sources CSV, Hyper ou SQL selon le contexte.

Résultat attendu:
- un ensemble de tables brutes,
- des colonnes techniques exploitables,
- un catalogue minimal des connexions et sources.

### 3. Détection des éléments utilisés dans les visuels
Sous-étapes:
- analyser les worksheets,
- lire les shelves `rows`, `columns`, `marks` et filtres,
- associer les champs aux tableaux et colonnes d’origine,
- marquer les colonnes réellement utilisées dans les dashboards,
- conserver aussi les éléments non utilisés pour le catalogue complet.

Résultat attendu:
- un indicateur d’usage par colonne,
- une couverture plus fidèle du modèle,
- une base claire pour les phases semantiques et RDL.

### 4. Normalisation du modèle
Sous-étapes:
- convertir les structures extraites vers les modèles Pydantic universels,
- harmoniser les noms de tables et colonnes,
- stabiliser les références de colonnes et relations,
- remplir les champs standardisés (`role`, `is_used_in_dashboard`, `label`, etc.),
- préparer les objets `Table`, `Column`, `Relationship`, `MetadataModel`.

Résultat attendu:
- un modèle unique, sérialisable et homogène,
- indépendant des détails du connecteur source,
- réutilisable par les phases suivantes.

### 5. Profiling optionnel des colonnes
Sous-étapes:
- calculer les statistiques utiles sur un échantillon limité,
- mesurer la cardinalité (`distinct_count`),
- calculer la proportion de valeurs nulles (`null_ratio`),
- détecter les colonnes dominantes et les anomalies simples,
- enrichir le catalogue avec des signaux de qualité.

Résultat attendu:
- des métadonnées de qualité,
- une meilleure préparation pour le classement mesure/dimension,
- des signaux supplémentaires pour la phase sémantique.

### 6. Détection des relations
Sous-étapes:
- exploiter les relations SQL si elles sont disponibles,
- détecter les jointures implicites à partir des clés et suffixes,
- compléter avec des heuristiques métier simples,
- normaliser les liens entre tables et colonnes,
- stocker les relations dans le modèle universel.

Résultat attendu:
- un graphe relationnel minimal mais exploitable,
- une base pour la reconstruction du schéma logique,
- un support pour le catalogue et les visuels liés.

### 7. Construction du catalogue
Sous-étapes:
- exposer les tables et colonnes disponibles,
- conserver les colonnes visibles et invisibles,
- préparer les métadonnées nécessaires au drag & drop,
- fournir un accès uniforme aux colonnes de source.

Résultat attendu:
- un catalogue de colonnes stable,
- prêt pour la sélection métier,
- compatible avec les usages d’assistance à la modélisation.

### 8. Export des résultats
Sous-étapes:
- sérialiser le modèle normalisé en JSON,
- produire une version YAML si nécessaire,
- journaliser les warnings et anomalies,
- écrire les artefacts dans le répertoire de sortie.

Résultat attendu:
- un artefact de sortie consommable automatiquement,
- un format lisible pour le debug et l’archivage.

### 9. Orchestration et cache
Sous-étapes:
- vérifier le cache avant de refaire l’extraction,
- réutiliser les résultats si le contenu semantique n’a pas changé,
- éviter les recalculs inutiles,
- conserver un pipeline déterministe autant que possible.

Résultat attendu:
- exécution plus rapide sur les entrées répétées,
- stabilité des sorties,
- réduction des appels coûteux.

## Structure des modules
```
phase0_extraction/
├── adapters/                # Détection et extraction (Tableau, RDL)
├── readers/                 # Lecture Hyper/SQL/CSV
├── normalization/           # Normalisation → MetadataModel
├── enrichment/              # Profiling colonnes
├── relationship_detection/  # Détection relations
├── registry/                 # Catalogue
├── export/                   # Export JSON/YAML
├── pipeline.py               # Orchestrateur principal
├── models.py                 # Modèle Pydantic universel
└── tests/                    # Tests unitaires
```

## Modèle de données universel
- Voir `models.py` pour la structure complète (`Column`, `Table`, `Relationship`, `MetadataModel`)
- Champs clés: `is_used_in_dashboard`, `role`, `distinct_count`, `null_ratio`, `extraction_warnings`

## Usage rapide
```python
from viz_agent.phase0_extraction.pipeline import MetadataExtractor

extractor = MetadataExtractor()
model = extractor.extract("/path/to/source.twbx", enable_profiling=True)

print(model.tables)
print(model.relationships)
```

## Tests
- Tous les modules sont couverts par des tests unitaires (voir dossier `tests/`)
- Lancer tous les tests:
    ```powershell
    powershell -ExecutionPolicy Bypass -File run_all_tests.ps1
    ```

## Spécifications détaillées
- Voir le prompt complet dans `Prompts/prompt_metadata_extraction_v2.md`
- Respect strict du modèle et des signatures
- Gestion des erreurs robuste: warnings, jamais d’exception non catchée
