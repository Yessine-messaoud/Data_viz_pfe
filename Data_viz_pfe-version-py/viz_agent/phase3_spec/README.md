# Phase 3 — Construction de l’Abstract Spec

## Objectif
Générer l’Abstract Spec (spécification abstraite du dashboard) à partir du modèle sémantique et du workbook parsé. Préparer la structure pour la génération RDL.

## Fonctionnalités principales
- **Construction de l’Abstract Spec** à partir du modèle sémantique
- **Gestion des rôles et des collisions** sur les colonnes
- **Création des pages, visuels, bindings, filtres, etc.**
- **Indexation des rôles** pour chaque colonne
- **Préparation des objets pour la validation et la génération RDL**

## Structure des modules
- `abstract_spec_builder.py` : Construction de l’Abstract Spec
- `specification_agent.py` : Agent de spécification
- `components/` : Composants de l’Abstract Spec

## Usage rapide
```python
from viz_agent.phase3_spec.abstract_spec_builder import DashboardSpecFactory
spec = DashboardSpecFactory.build(semantic_model, parsed_workbook)
```

## Notes
- L’Abstract Spec est validé à la phase suivante avant toute génération RDL.