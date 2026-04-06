# AMÉ LIORATION DE LA PHASE 3 - ABSTRACT SPEC V2

## ✅ Problème résolu

Le problème principal était que **le pie chart était généré comme un Chart générique au lieu d'un PieChart spécifique**.

### Avant (Problématique)
```json
{
  "visualization": {
    "type": "pie",  // ✓ Type correct
    "encoding": {}
  },
  "rendering": {
    "rdl_type": "chart"  // ✗ Type générique (problème)
  }
}
```

Le RDL generator créait un `<Chart>` sans subtypes spécifiques.

###  Après (Corrigé)
```json
{
  "visualization": {
    "type": "pie",  // ✓ Type spécifique
    "encoding": { "y": {...} }  // ✓ Encoding correct
  },
  "rendering": {
    "rdl_type": "PieChart",  // ✓ RDL spécifique
    "chart_type": "Pie"      // ✓ Subtype chart spécifié
  }
}
```

Le RDL generator créera maintenant un `<Chart Type="Pie">` avec configuration adéquate.

---

## 📊 Structure Améliorée

```
viz_agent/phase3_spec/v2_improved/
├── models/
│   ├── __init__.py
│   └── visualization_model.py
│       - VisualizationType (strict enum: bar, line, pie, treemap, scatter, table, kpi, map, gantt)
│       - EncodingSpec (x, y, color, size, details)
│       - VisualizationSpec (business layer)
│       - DataSpec (data binding)
│       - RenderingSpec (RDL-specific)
│       - VisualSpecV2 (complete with separation of concerns)
│
├── mappers/
│   ├── __init__.py
│   └── visualization_mapper.py
│       - TABLEAU_TO_LOGICAL: Tableau mark → logical type
│       - LOGICAL_TO_RDL: logical type → RDL type (PieChart, ColumnChart, etc.)
│       - RDL_CHART_SUBTYPES: RDL type → Chart subtype (Pie, Column, Line, etc.)
│       - VisualizationMapper.full_chain() : complet mapping
│       - EncodingRequirements: validation des encodings requis
│
├── validators/
│   ├── __init__.py
│   ├── spec_validator.py
│   │   - VisualSpecV2Validator: stricte validation
│   │   - SpecValidator: batch validation
│   ├── spec_autofix.py
│   │   - SpecAutoFixer.autofix_visual(): auto-correction d'un visual
│   │   - SpecAutoFixer.autofix_dashboard(): auto-correction en batch
│   └── schemas.py
│       - JSON Schemas pour jsonschema validation
│
└── example_usage.py
    - Examples complets de mapping et auto-fix
```

---

## 🔄 Mapping Chain (Strict)

### Exemple: Pie Chart

```
Tableau Mark: "Pie"
    ↓
Logical Type: "pie"  (inféré de TABLEAU_TO_LOGICAL)
    ↓
RDL Type: "PieChart"  (depuis LOGICAL_TO_RDL)
    ↓
Chart Subtype: "Pie"  (depuis RDL_CHART_SUBTYPES)
```

### Autres Mappings

| Tableau | Logical | RDL | Chart Type |
|---------|---------|-----|------------|
| Pie | pie | PieChart | Pie |
| Bar | bar | ColumnChart | Column |
| Line | line | LineChart | Line |
| Treemap | treemap | TreeMap | None |
| Circle | scatter | ScatterChart | Scatter |
| Text | table | Tablix | None |

---

## 🔧 Auto-Fix Automatique

Le système détecte et corrige automatiquement:

1. **Generic 'chart' type** → Détecte, inférer depuis Tableau mark
2. **RDL type mismatch** → Corriger pour correspondre au type visual
3. **Missing encoding axes** → Ajouter encoding requis (pie: y, bar: x+y)
4. **Missing fact_table** → Ajouter référence à la table de données

### Exemple de Correction

```python
from viz_agent.phase3_spec.v2_improved.validators.spec_autofix import SpecAutoFixer

broken_spec = {
    "visualization": {"type": "chart"},  # BROKEN
    "rendering": {"rdl_type": "chart"},  # BROKEN
    # ...
}

fixed, changes = SpecAutoFixer.autofix_visual(broken_spec, tableau_mark="Pie")
# Changes: 
# - "Fixed generic 'chart' type to 'pie'"
# - "Fixed RDL type mismatch: chart → PieChart"

print(fixed["visualization"]["type"])  # "pie"
print(fixed["rendering"]["rdl_type"])  # "PieChart"
```

---

## ✅ Validation: Pas d'erreurs silencieuses

Le système lève des erreurs explicites pour:

- Generic "chart" type → ValueError
- RDL type mismatch → ValidationIssue avec fix suggestions
- Missing required encoding → ValidationIssue  
- Invalid visualization type → Pydantic ValidationError

---

## 🚀 Intégration avec le Pipeline Existant

### Étape 1: Charger abstract spec depuis JSON

```python
import json
from viz_agent.phase3_spec.v2_improved.validators.spec_autofix import SpecAutoFixer
from viz_agent.phase3_spec.v2_improved.validators.spec_validator import SpecValidator

# Load generated spec
with open("demo1_2_demo_abstract_spec.json") as f:
    abstract_spec = json.load(f)

# Auto-fix dashboard
fixed_dashboard, report = SpecAutoFixer.autofix_dashboard(
    abstract_spec["dashboard_spec"]
)

print(f"Fixed {report['fixed_visuals']} visuals")

# Update abstract spec
abstract_spec["dashboard_spec"] = fixed_dashboard
```

### Étape 2: Utiliser dans RDL Generator

```python
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
from viz_agent.phase5_rdl.rdl_visual_mapper import RDLVisualMapper

# RDL generator should now use the corrected rdl_type and chart_type
mapper = RDLVisualMapper(llm_client=llm, semantic_model=abstract_spec["semantic_model"])

for visual in fixed_dashboard["pages"][0]["visuals"]:
    # Visual now has correct rendering.rdl_type = "PieChart"
    # And rendering.chart_type = "Pie"
    rdl_element = mapper.map_visual(visual, dataset, rect)
```

---

## 📋 Schémas JSON Disponibles

Tous les schémas sont dans `schemas.py`:

- `encoding_axis.schema.json`
- `encoding_spec.schema.json`
- `visualization_spec.schema.json`
- `data_spec.schema.json`
- `rendering_spec.schema.json`
- `visual_spec_v2.schema.json`
- `dashboard_spec_v2.schema.json`

Utilisation:

```python
from viz_agent.phase3_spec.v2_improved.validators.schemas import get_schema_string
schema = get_schema_string("visual_spec_v2")
```

---

## 🎯 Bénéfices

✅ **Pas de "chart" générique** - Types spécifiques (PieChart, ColumnChart, LineChart, etc.)
✅ **Séparation claire** - visualization, encoding, data, rendering layers
✅ **Auto-correction** - Détection et correction automatique des erreurs communes
✅ **Validation stricte** - Erreurs explicites, pas de silent fallback
✅ **Extensible** - Facile ajouter nouveaux types de visualisations
✅ **Pipeline-ready** - Compatible avec validation en loop et correction itérative

---

## ⚙️ Paramètres de Configuration

Les visuals corrigés sont maintenant prêts pour:
- **RDL Generation** avec Chart subtypes spécifiques
- **Visualization Planning** avec encoding requis validé
- **Data Lineage** avec fact_table explicite
- **Validation en boucle** sans dégradation progressive

---

## 📝 Résumé des Fichiers Créés

1. **visualization_model.py** - Modèles Pydantic stricts
2. **visualization_mapper.py** - Mappings Tableau → RDL stricts
3. **spec_validator.py** - Validation stricte des specs
4. **spec_autofix.py** - Auto-correction automatique
5. **schemas.py** - Schémas JSON pour validation jsonschema
6. **example_usage.py** - Exemples complets d'utilisation
