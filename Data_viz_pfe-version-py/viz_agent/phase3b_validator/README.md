# Phase 3b — Validation de l’Abstract Spec

## Objectif
Valider l’Abstract Spec généré avant la génération du rapport RDL. Détecter les erreurs bloquantes et les avertissements pour garantir la qualité du dashboard.

## Fonctionnalités principales
- **Validation des tables inconnues**
- **Vérification des IDs de colonnes brutes**
- **Détection des datasets RDL vides**
- **Vérification de la table de faits**
- **Détection des pages dupliquées**
- **Vérification des axes vides**
- **Détection des types de visuels personnalisés**
- **Détection des tables fantômes**
- **Calcul du score de validation**
- **Blocage du pipeline si erreurs critiques**

## Structure des modules
- `abstract_spec_validator.py` : Validateur principal

## Usage rapide
```python
from viz_agent.phase3b_validator.abstract_spec_validator import AbstractSpecValidator
validator = AbstractSpecValidator()
report = validator.validate(spec)
if not report.can_proceed:
    print(report.errors)
```

## Notes
- Les erreurs bloquantes empêchent la génération du RDL.
- Les avertissements sont remontés mais n’arrêtent pas le pipeline.