# Phase 1 — Parsing du Workbook Tableau

## Objectif
Extraire et parser toutes les entités d’un workbook Tableau (.twbx) : worksheets, dashboards, calculs, paramètres, filtres, palettes, etc. pour les transformer en objets Python structurés.

## Fonctionnalités principales
- **Chargement du XML** du workbook Tableau
- **Parsing des worksheets** (feuilles de calcul)
- **Parsing des datasources** (sources de données)
- **Parsing des dashboards** (tableaux de bord)
- **Extraction des champs calculés**
- **Extraction des paramètres et filtres**
- **Gestion des palettes de couleurs**
- **Transformation** en objets `ParsedWorkbook` pour la suite du pipeline

## Structure des modules
- `tableau_parser.py` : Parsing principal du workbook
- `column_decoder.py` : Décodage des références de colonnes
- `dashboard_zone_mapper.py` : Extraction des worksheets utilisées dans les dashboards
- `visual_type_mapper.py` : Mapping des types de visuels Tableau → RDL
- `federated_resolver.py` : Résolution des sources fédérées

## Usage rapide
```python
from viz_agent.phase1_parser.tableau_parser import TableauParser
parser = TableauParser()
parsed = parser.parse('workbook.twbx', registry)
```

## Notes
- Le parser s’appuie sur lxml pour le parsing XML.
- Les objets extraits sont typés (Pydantic) et utilisés dans les phases suivantes.