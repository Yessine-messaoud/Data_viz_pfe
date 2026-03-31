# Phase 6 — Export du Lineage

## Objectif
Exporter le lineage des données (tables, colonnes, relations) au format JSON pour la traçabilité et l’audit des flux BI.

## Fonctionnalités principales
- **Export du lineage** au format JSON
- **Liste des tables et des jointures**
- **Génération de requêtes SELECT * pour chaque table**
- **Support de l’audit et de la traçabilité**

## Structure des modules
- `lineage_service.py` : Service principal d’export et de requêtage du lineage

## Usage rapide
```python
from viz_agent.phase6_lineage.lineage_service import LineageQueryService
service = LineageQueryService(lineage)
print(service.to_json())
```

## Notes
- Le lineage est utilisé pour la traçabilité des transformations et la documentation BI.