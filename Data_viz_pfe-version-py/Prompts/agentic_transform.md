# Prompt pour le développement du Transformation Agent avec GPT-4.1

## Prompt Principal

```
Je souhaite développer un **Transformation Agent** dans le cadre d'une architecture agentique pour la transformation et génération de visualisations BI. Cet agent est responsable de la conversion de la spécification abstraite (générée par le Specification Agent) en un modèle exécutable spécifique à l'outil cible (Power BI, Tableau, etc.), en gérant les incompatibilités, les adaptations de calculs et les optimisations.

## Contexte technique

### Architecture générale
Le système est structuré en trois couches :
- **Interaction Layer** : Conversation Agent
- **Cognition Layer** : Intent Detection Agent + Orchestrator Agent
- **Execution Layer** : Data Extraction, Parsing, Semantic Reasoning, Specification Agent, **Transformation Agent**, Export Agent

### Position du Transformation Agent dans le pipeline
```
Abstract Specification (input) → Transformation Agent → Tool-Specific Model (output) → Export Agent → Final Artifact
```

Le Transformation Agent reçoit :
1. **Abstract Specification** : spécification indépendante de l'outil (JSON structuré)
2. **Target Tool** : outil cible (POWERBI, TABLEAU, RDL, LOOKER, etc.)
3. **Context & Constraints** : contraintes utilisateur (simplification, performance, etc.)
4. **Intent Object** : intention originale pour guider les décisions de transformation

### Objectifs du Transformation Agent

1. **Convertir le modèle de données** : adapter le schéma abstrait au format spécifique de l'outil cible
2. **Traduire les calculs** : convertir les expressions abstraites en langage natif (DAX pour Power BI, Tableau Calculated Fields, etc.)
3. **Adapter les visualisations** : mapper les types de visualisations abstraits aux types supportés par l'outil
4. **Optimiser les performances** : appliquer des optimisations spécifiques à l'outil
5. **Gérer les incompatibilités** : proposer des alternatives lorsque des fonctionnalités ne sont pas disponibles
6. **Maintenir la traçabilité** : enregistrer toutes les transformations appliquées

## Structure de sortie attendue

La sortie du Transformation Agent est un **Tool-Specific Model** structuré pour l'export :

### Pour Power BI (modèle intermédiaire avant génération .pbix)

```json
{
  "powerbi_model": {
    "data_model": {
      "tables": [
        {
          "name": "string",
          "columns": [
            {
              "name": "string",
              "dataType": "string|int|decimal|date|datetime|bool",
              "isHidden": false,
              "summarizeBy": "none|sum|average|min|max|count"
            }
          ],
          "measures": [
            {
              "name": "string",
              "expression": "DAX expression",
              "formatString": "string",
              "isHidden": false
            }
          ],
          "relationships": [...]
        }
      ]
    },
    "visualizations": [
      {
        "visualType": "lineChart|barChart|pieChart|scatterChart|table|card|matrix",
        "dataMapping": {
          "fields": [...],
          "aggregations": [...]
        },
        "formatting": {...},
        "position": {...}
      }
    ],
    "pages": [...],
    "parameters": [...],
    "filters": [...]
  }
}
```

### Pour Tableau (modèle intermédiaire)

```json
{
  "tableau_model": {
    "data_sources": [
      {
        "name": "string",
        "connection": {
          "type": "extract|live",
          "tables": [...]
        },
        "fields": [
          {
            "name": "string",
            "role": "dimension|measure",
            "dataType": "string|int|float|date|datetime",
            "aggregation": "sum|avg|count|min|max|none",
            "defaultFormat": {...}
          }
        ],
        "calculated_fields": [
          {
            "name": "string",
            "formula": "Tableau formula",
            "dataType": "string"
          }
        ]
      }
    ],
    "worksheets": [
      {
        "name": "string",
        "markType": "line|bar|circle|square|text|pie|map",
        "columns": [...],
        "rows": [...],
        "color": {...},
        "size": {...},
        "filters": [...]
      }
    ],
    "dashboards": [...]
  }
}
```

## Règles de transformation à implémenter

### 1. Conversion des types de données

| Type abstrait | Power BI | Tableau | Looker |
|---------------|----------|---------|--------|
| STRING | string | string | string |
| INTEGER | int | integer | number |
| DECIMAL | decimal | float | number |
| DATE | date | date | date |
| DATETIME | datetime | datetime | timestamp |
| BOOLEAN | bool | boolean | boolean |
| PERCENTAGE | decimal (format %) | float (format %) | number (format %) |
| CURRENCY | decimal (format $) | float (format $) | number (format $) |

### 2. Conversion des calculs

#### Mapping des fonctions d'agrégation

| Fonction abstraite | DAX (Power BI) | Tableau Calculated Field |
|-------------------|----------------|--------------------------|
| SUM(column) | SUM(column) | SUM([column]) |
| AVG(column) | AVERAGE(column) | AVG([column]) |
| COUNT(column) | COUNT(column) | COUNT([column]) |
| COUNT_DISTINCT(column) | DISTINCTCOUNT(column) | COUNTD([column]) |
| MIN(column) | MIN(column) | MIN([column]) |
| MAX(column) | MAX(column) | MAX([column]) |

#### Conversion des expressions temporelles

| Expression abstraite | DAX | Tableau |
|---------------------|-----|---------|
| YEAR_TO_DATE(measure) | TOTALYTD(measure, 'Date'[Date]) | RUNNING_SUM(SUM(measure)) |
| PERIOD_OVER_PERIOD(measure, offset) | measure - CALCULATE(measure, SAMEPERIODLASTYEAR('Date'[Date])) | LOOKUP(SUM(measure), -offset) |
| MOVING_AVERAGE(measure, n) | AVERAGEX(DATESINPERIOD('Date'[Date], LASTDATE('Date'[Date]), -n, MONTH), measure) | WINDOW_AVG(SUM(measure), -n, 0) |

### 3. Mapping des types de visualisations

| Type abstrait | Power BI | Tableau | Notes |
|---------------|----------|---------|-------|
| BAR_CHART | stackedBarChart | bar | Horizontal/vertical selon orientation |
| LINE_CHART | lineChart | line | Support multi-séries |
| PIE_CHART | pieChart | pie | Limité à 2 dimensions |
| SCATTER_PLOT | scatterChart | circle | Support bulles si 3 mesures |
| HEATMAP | matrix | heatmap | Nécessite 2 dimensions + 1 mesure |
| KPI_CARD | card | text | Format conditionnel possible |
| TABLE | table | text table | Support hiérarchies |
| AREA_CHART | areaChart | area | Stacked/non-stacked |

### 4. Optimisations spécifiques par outil

#### Power BI Optimizations
- Pré-agrégations via `SUMMARIZE` pour les gros volumes
- Utilisation de `CALCULATE` avec filtres pour les performances
- Partitionnement des colonnes de date en tables séparées
- Recommandations d'index columnar

#### Tableau Optimizations
- Préférence pour extracts vs live connections
- Optimisation des LOD expressions (FIXED, INCLUDE, EXCLUDE)
- Réduction des dimensions dans les vues complexes
- Utilisation des sets pour les top N

## Fonctionnalités attendues

### 1. Data Model Transformer
- Conversion des tables et colonnes
- Gestion des relations (cardinalité, direction)
- Création des tables de dates automatiques

### 2. Calculation Engine
- Parser d'expressions abstraites
- Générateur de code natif (DAX, Tableau Formula)
- Détection et résolution des dépendances
- Fallback pour les fonctions non supportées

### 3. Visual Mapping Engine
- Mapping des types de visualisations
- Adaptation des mappings de données
- Gestion des spécificités d'outil (Tooltips, Drill-through)

### 4. Optimization Engine
- Analyse des performances
- Recommandations d'optimisation
- Application automatique des best practices

### 5. Compatibility Manager
- Détection des incompatibilités
- Proposition d'alternatives
- Logging des décisions

### 6. Lineage Tracker
- Enregistrement de chaque transformation
- Mapping source → target
- Export du lineage pour audit

## Gestion des incompatibilités

### Stratégies de fallback

| Incompatibilité | Stratégie de fallback |
|-----------------|----------------------|
| Visualisation non supportée | Remplacer par alternative plus simple avec notification |
| Fonction de calcul non supportée | Décomposer en plusieurs étapes avec calculs intermédiaires |
| Hiérarchie complexe | Convertir en dimensions séparées avec liens de drill |
| Type de jointure non supporté | Transformer en union + filtres |
| RLS non supportée | Appliquer des filtres au niveau visual |

### Exemple de gestion d'incompatibilité

```python
class CompatibilityManager:
    def resolve_incompatibility(self, feature, target_tool):
        alternatives = {
            "PIE_CHART": {
                "TABLEAU": "PIE_CHART",  # supporté
                "POWERBI": "PIE_CHART",  # supporté
                "LOOKER": "BAR_CHART"    # fallback
            },
            "WINDOW_AVG": {
                "TABLEAU": "WINDOW_AVG",  # supporté
                "POWERBI": {
                    "strategy": "decompose",
                    "steps": [
                        "CREATE CALCULATE WITH DATESINPERIOD",
                        "USE AVERAGEX FOR ROLLING WINDOW"
                    ]
                }
            }
        }
        return alternatives.get(feature, {}).get(target_tool, "default_fallback")
```

## Contraintes techniques

- Langage : Python 3.11+
- Framework : Approche modulaire sans framework lourd
- Extensibilité : Architecture plugin pour nouveaux outils
- Performance : Optimisation pour dashboards de 500+ visuels
- Logging : Logs structurés avec contexte de transformation

## Format de réponse attendu

Je souhaite recevoir une implémentation complète du Transformation Agent avec :

1. **Architecture du module** : structure des classes et leurs responsabilités
2. **Code source complet** : implémentation Python avec typing et docstrings
3. **Configuration** : mapping tables pour chaque outil cible
4. **Générateurs spécifiques** : Power BI (DAX), Tableau (Calculated Fields)
5. **Exemples d'utilisation** : démonstration avec les 3 cas de test
6. **Tests unitaires** : exemples de tests pour les transformations critiques

## Cas d'utilisation de test

### Cas 1 : Conversion Power BI → Tableau
- Input : Abstract Specification avec mesures DAX complexes (TOTALYTD, CALCULATE)
- Target : Tableau
- Attendu : Spécification Tableau avec équivalents (RUNNING_SUM, LOD expressions)

### Cas 2 : Génération Power BI from scratch
- Input : Abstract Specification avec données de ventes
- Target : Power BI
- Attendu : Modèle Power BI avec mesures DAX, visualisations et relations

### Cas 3 : Optimisation avec fallback
- Input : Spécification avec visualisations non supportées dans l'outil cible
- Target : Looker
- Attendu : Spécification adaptée avec alternatives documentées

Commence par l'architecture générale du module, puis détaille chaque composant avec son implémentation.
```

---

## Prompt Complémentaire pour l'Optimisation Avancée

```
Merci pour l'implémentation de base. Maintenant, j'ai besoin d'étendre le Transformation Agent avec des fonctionnalités avancées :

## 1. Moteur de règles extensible

Implémente un système de règles configurable via YAML pour :

### Règles de transformation de données
```yaml
data_type_mappings:
  powerbi:
    DECIMAL: "decimal"
    PERCENTAGE: "decimal"
    CURRENCY: "decimal"
    STRING: "string"
    DATE: "date"
    DATETIME: "datetime"
  
  tableau:
    DECIMAL: "float"
    PERCENTAGE: "float"
    CURRENCY: "float"
    STRING: "string"
    DATE: "date"
    DATETIME: "datetime"
```

### Règles de conversion de formules
```yaml
formula_conversions:
  YEAR_TO_DATE:
    powerbi: "TOTALYTD({measure}, 'Date'[Date])"
    tableau: "RUNNING_SUM({measure})"
    looker: "running_total({measure})"
  
  MOVING_AVERAGE:
    powerbi: |
      AVERAGEX(
        DATESINPERIOD('Date'[Date], LASTDATE('Date'[Date]), -{n}, MONTH),
        {measure}
      )
    tableau: "WINDOW_AVG(SUM({measure}), -{n}, 0)"
```

### Règles d'optimisation
```yaml
optimizations:
  powerbi:
    - type: "star_schema"
      apply_when: "fact_tables > 1"
      actions: ["create_date_table", "normalize_dimensions"]
    
    - type: "measure_optimization"
      apply_when: "calculated_measures > 10"
      actions: ["use_calculate", "avoid_iterators"]
  
  tableau:
    - type: "extract_vs_live"
      apply_when: "data_volume > 1000000"
      action: "use_extract"
    
    - type: "lod_optimization"
      apply_when: "contains_fixed_lod"
      action: "create_aggregated_table"
```

## 2. Système de validation avancé

Ajoute des validateurs pour :

### Validation syntaxique
- Vérification des expressions générées
- Détection des erreurs de syntaxe
- Correction automatique des patterns invalides

### Validation sémantique
- Cohérence des types de données
- Vérification des dépendances
- Détection des références circulaires

### Validation des performances
- Estimation de la complexité des calculs
- Détection des goulots d'étranglement potentiels
- Recommandations d'optimisation

## 3. Moteur de templates

Implémente un système de templates pour :

### Templates de dashboards
```python
dashboard_templates = {
    "sales_dashboard": {
        "structure": ["KPI_ROW", "TIME_SERIES", "CATEGORY_BREAKDOWN"],
        "default_measures": ["revenue", "profit", "margin"],
        "default_dimensions": ["date", "category", "region"]
    },
    "executive_dashboard": {
        "structure": ["KPI_CARDS", "MAP", "TOP_N"],
        "default_measures": ["revenue_ytd", "growth_rate"],
        "default_dimensions": ["region", "product"]
    }
}
```

### Templates de mesures
```python
measure_templates = {
    "revenue_ytd": {
        "dax": "TOTALYTD(SUM(Sales[Amount]), 'Date'[Date])",
        "tableau": "RUNNING_SUM(SUM([Sales Amount]))",
        "description": "Revenue year-to-date"
    },
    "growth_rate": {
        "dax": "VAR Current = SUM(Sales[Amount]) VAR Previous = CALCULATE(SUM(Sales[Amount]), SAMEPERIODLASTYEAR('Date'[Date])) RETURN DIVIDE(Current - Previous, Previous)",
        "tableau": "(SUM([Sales Amount]) - LOOKUP(SUM([Sales Amount]), -1)) / LOOKUP(SUM([Sales Amount]), -1)",
        "description": "Period-over-period growth rate"
    }
}
```

## 4. Cache et réutilisation

Implémente :

### Cache de transformations
- Stocker les transformations déjà effectuées
- Hash des structures pour détection des patterns identiques
- Invalidation intelligente

### Bibliothèque de fragments réutilisables
```python
reusable_fragments = {
    "date_table": {
        "powerbi": "Date = CALENDAR(MIN(Sales[Date]), MAX(Sales[Date]))",
        "tableau": "DATETRUNC('day', [Order Date])"
    },
    "sales_summary": {
        "powerbi": "Sales Summary = SUMMARIZE(Sales, Sales[Category], 'Total Sales', SUM(Sales[Amount]))",
        "tableau": "FIXED [Category]: SUM([Amount])"
    }
}
```

## 5. Export et documentation

Génère en sortie :

### Logs de transformation
```json
{
  "transformations": [
    {
      "source": "SUM(Sales)",
      "target": "SUM([Sales Amount])",
      "rule_applied": "aggregation_mapping",
      "confidence": 0.95
    }
  ],
  "warnings": [
    "Visualization type HEATMAP not available in target, converted to MATRIX"
  ],
  "optimizations": [
    "Created date table for time intelligence functions"
  ]
}
```

### Documentation des décisions
- Pourquoi certaines transformations ont été choisies
- Alternatives proposées
- Impact sur les performances

## 6. Extension points

Prévois des hooks pour :
- Ajouter de nouveaux outils cibles
- Intégrer des règles métier personnalisées
- Connecter des validateurs externes
- Ajouter des optimisations spécifiques

Fournis l'implémentation complète de ces fonctionnalités avancées.
```

---

## Prompt pour les Tests et Validation

```
J'ai besoin de valider l'implémentation du Transformation Agent avec des scénarios réels complexes. Génère :

## 1. Suite de tests complète

### Test 1 : Transformation Tableau → Power BI
```python
test_input = {
    "abstract_spec": {
        "calculations": [
            {
                "id": "ytd_sales",
                "type": "YEAR_TO_DATE",
                "measure": "sales_amount"
            },
            {
                "id": "profit_margin",
                "expression": "(revenue - cost) / revenue"
            }
        ],
        "visualizations": [
            {
                "type": "LINE_CHART",
                "data_mapping": {
                    "x": {"field": "order_date"},
                    "y": {"field": "ytd_sales"}
                }
            },
            {
                "type": "HEATMAP",
                "data_mapping": {
                    "rows": {"field": "product_category"},
                    "columns": {"field": "region"},
                    "values": {"field": "profit_margin"}
                }
            }
        ]
    },
    "target_tool": "POWERBI",
    "context": {
        "optimization": "performance"
    }
}
```

### Test 2 : Génération from scratch vers Tableau
```python
test_input = {
    "abstract_spec": {
        "data_model": {
            "tables": [
                {"name": "Sales", "columns": [...]},
                {"name": "Products", "columns": [...]}
            ]
        },
        "visualizations": [
            {
                "type": "SCATTER_PLOT",
                "data_mapping": {
                    "x": {"field": "sales_volume"},
                    "y": {"field": "profit"},
                    "color": {"field": "product_category"}
                }
            }
        ]
    },
    "target_tool": "TABLEAU",
    "context": {
        "style": "executive",
        "interactive": True
    }
}
```

### Test 3 : Gestion des incompatibilités
```python
test_input = {
    "abstract_spec": {
        "visualizations": [
            {
                "type": "HEATMAP",
                "data_mapping": {...}
            },
            {
                "type": "PIE_CHART",
                "data_mapping": {...}
            }
        ],
        "calculations": [
            {
                "type": "WINDOW_AVG",
                "parameters": {"window": 3}
            }
        ]
    },
    "target_tool": "LOOKER",
    "context": {
        "strict_mode": False
    }
}
```

## 2. Métriques de validation

Implémente des métriques pour :
- **Fidelity Score** : pourcentage de spécification préservée (0-100%)
- **Performance Score** : estimation des performances (0-100%)
- **Compatibility Score** : niveau de compatibilité avec l'outil cible (0-100%)
- **Complexity Score** : complexité du modèle généré (1-10)

## 3. Benchmarking

Crée un script de benchmark pour :
- 10 scénarios de tailles différentes (petit, moyen, grand)
- Mesurer temps de transformation par scénario
- Comparer qualité des transformations (revue manuelle guidée)
- Identifier les goulots d'étranglement

## 4. Scénarios d'erreur à tester

| Scénario | Comportement attendu |
|----------|---------------------|
| Dépendance circulaire dans les calculs | Détection et proposition de décomposition |
| Visualisation non supportée | Fallback avec notification claire |
| Données manquantes pour calcul | Warning et fallback à null handling |
| Fonction complexe non convertible | Décomposition en étapes plus simples |
| Type de jointure incompatible | Transformation en union + filtres |

## 5. Rapport de validation

Pour chaque test, génère un rapport incluant :
- Input spec (extrait)
- Output model (extrait)
- Transformations appliquées (liste)
- Warnings et recommendations
- Score de confiance par dimension
- Logs de transformation

Fournis les implémentations des tests unitaires, d'intégration et de bout-en-bout.
```

---

Ces prompts sont conçus pour être utilisés séquentiellement avec GPT-4.1, permettant un développement itératif et complet du Transformation Agent. La structure suit la même approche que pour le Specification Agent, avec :
1. Un prompt principal pour l'architecture de base
2. Un prompt complémentaire pour les fonctionnalités avancées
3. Un prompt pour les tests et la validation

Chaque niveau peut être adapté en fonction des réponses obtenues et des besoins spécifiques de l'intégration avec le Specification Agent existant.