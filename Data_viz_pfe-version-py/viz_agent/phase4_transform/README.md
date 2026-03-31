# Phase 4 — Traduction des Champs Calculés

## Objectif
Traduire les champs calculés Tableau en expressions RDL valides pour l’intégration dans le rapport paginé.

## Fonctionnalités principales
- **Traduction automatique** des expressions calculées Tableau → RDL
- **Gestion des cas non traduisibles** (`__UNTRANSLATABLE__`)
- **Utilisation de règles strictes** pour la syntaxe RDL
- **Support des ratios, agrégations, COUNTD, etc.**
- **Overrides pour certains calculs connus**

## Structure des modules
- `calc_field_translator.py` : Traduction principale
- `rdl_dataset_mapper.py` : Mapping des datasets pour RDL
- `agent/` : Agents de traduction avancée

## Usage rapide
```python
from viz_agent.phase4_transform.calc_field_translator import TableauCalcFieldTranslator
translator = TableauCalcFieldTranslator(llm_client)
rdl_expr = translator.translate(tableau_expr, tables_context)
```

## Notes
- Utilise un LLM pour la traduction avancée.
- Retourne `__UNTRANSLATABLE__` si la traduction est impossible.