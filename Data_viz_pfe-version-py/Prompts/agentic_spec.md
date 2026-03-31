# Prompt pour le développement du Specification Agent avec GPT-4.1

## Prompt Principal

```
Je souhaite développer un **Specification Agent** dans le cadre d'une architecture agentique pour la transformation et génération de visualisations BI. Cet agent est responsable de la génération d'une spécification abstraite, indépendante de l'outil cible, à partir du graphe sémantique produit par le Semantic Reasoning Agent.

## Contexte technique

### Architecture générale
Le système est structuré en trois couches :
- **Interaction Layer** : Conversation Agent (interprétation requête utilisateur)
- **Cognition Layer** : Intent Detection Agent + Orchestrator Agent
- **Execution Layer** : Data Extraction, Parsing, Semantic Reasoning, **Specification Agent**, Transformation, Export

### Position du Specification Agent dans le pipeline
```
Semantic Graph (input) → Specification Agent → Abstract Specification (output) → Transformation Agent → Export Agent
```

Le Specification Agent reçoit :
1. **Semantic Graph** : graphe de connaissances contenant les entités, relations, logiques métier et intentions de visualisation
2. **Intent Object** : intention formalisée par l'Intent Detection Agent (conversion, génération, analyse, optimisation)
3. **Context & Preferences** : préférences utilisateur issues du Conversation Agent

### Objectifs du Specification Agent

1. **Normaliser le modèle de données** : convertir les entités du graphe sémantique en un modèle abstrait indépendant de l'outil
2. **Encoder la logique métier** : transformer les calculs complexes (DAX, Tableau formulas) en expressions abstraites
3. **Planifier les visualisations** : mapper les données aux types de visualisations appropriés
4. **Définir la présentation** : structurer le dashboard et appliquer les contraintes utilisateur
5. **Assurer la traçabilité** : maintenir le lineage des transformations

## Structure de sortie attendue

La spécification abstraite doit être un objet JSON structuré comme suit :

### 1. Abstract Data Model
```json
{
  "tables": [
    {
      "id": "string",
      "name": "string",
      "source": "string",
      "columns": [
        {
          "id": "string",
          "name": "string",
          "data_type": "STRING|INTEGER|DECIMAL|DATE|DATETIME|BOOLEAN",
          "semantic_type": "DIMENSION|MEASURE|TEMPORAL|MONETARY|GEOGRAPHIC",
          "aggregation": "SUM|AVG|COUNT|MIN|MAX|NONE"
        }
      ]
    }
  ],
  "relationships": [
    {
      "from": "string",
      "to": "string",
      "type": "ONE_TO_ONE|ONE_TO_MANY|MANY_TO_ONE|MANY_TO_MANY"
    }
  ],
  "calculated_fields": [
    {
      "id": "string",
      "name": "string",
      "expression": {
        "formula": "string",
        "dependencies": ["string"],
        "semantic_type": "PERCENTAGE|CURRENCY|RATIO|COUNT"
      }
    }
  ]
}
```

### 2. Visualization Model
```json
{
  "visualizations": [
    {
      "id": "string",
      "type": "BAR_CHART|LINE_CHART|PIE_CHART|SCATTER_PLOT|TABLE|KPI_CARD|HEATMAP|AREA_CHART",
      "intent": "string",
      "data_mapping": {
        "axis": {
          "x": {"field": "string", "aggregation": "string", "format": "string"},
          "y": {"field": "string", "aggregation": "string", "format": "string"}
        },
        "color": {"field": "string", "palette": "string"},
        "tooltip": ["string"]
      },
      "layout": {
        "position": "string",
        "size": "SMALL|MEDIUM|LARGE|FULL",
        "priority": "integer"
      },
      "interactions": {
        "drill_down": ["string"],
        "cross_filter": ["string"]
      }
    }
  ]
}
```

### 3. Business Logic Model
```json
{
  "calculations": [
    {
      "id": "string",
      "name": "string",
      "type": "AGGREGATION|TIME_INTELLIGENCE|COMPARISON|RANKING",
      "definition": {},
      "dependencies": ["string"]
    }
  ],
  "filters": [
    {
      "id": "string",
      "scope": "GLOBAL|PAGE|VISUAL",
      "condition": {
        "field": "string",
        "operator": "EQUALS|IN|GREATER_THAN|LESS_THAN|BETWEEN",
        "value": "any"
      }
    }
  ],
  "parameters": [
    {
      "id": "string",
      "name": "string",
      "type": "STRING|INTEGER|DATE",
      "default": "any",
      "range": []
    }
  ]
}
```

### 4. Presentation Model
```json
{
  "dashboard_structure": {
    "pages": [
      {
        "id": "string",
        "name": "string",
        "layout": "GRID|FLEX|STACKED",
        "zones": [
          {
            "id": "string",
            "type": "HEADER|MAIN|SIDEBAR|FOOTER",
            "content": ["string"]
          }
        ]
      }
    ]
  },
  "theming": {
    "color_scheme": {
      "primary": "string",
      "secondary": "string",
      "background": "string"
    },
    "responsive": {
      "breakpoints": ["DESKTOP", "TABLET", "MOBILE"]
    }
  }
}
```

### 5. Metadata & Confidence
```json
{
  "metadata": {
    "spec_id": "string",
    "created_at": "ISO8601",
    "source_intent": {
      "type": "CONVERSION|GENERATION|ANALYSIS|OPTIMIZATION",
      "original_request": "string"
    }
  },
  "confidence_score": {
    "overall": 0.0-1.0,
    "dimensions": {
      "data_model": 0.0-1.0,
      "visualizations": 0.0-1.0,
      "business_logic": 0.0-1.0,
      "presentation": 0.0-1.0
    },
    "warnings": ["string"],
    "recommendations": ["string"]
  },
  "lineage": {
    "field_lineage": [
      {
        "target": "string",
        "sources": ["string"],
        "transformations": ["string"]
      }
    ]
  }
}
```

## Règles de transformation à implémenter

### Règles de normalisation des types de données
- DATE → date, format ISO
- TIMESTAMP → datetime
- DECIMAL(10,2) → decimal avec précision conservée
- VARCHAR(255) → string

### Règles de détection des intentions de visualisation
Implémenter un système de scoring basé sur :
- Présence d'une dimension temporelle → privilégier LINE_CHART ou AREA_CHART
- 2 dimensions + 1 mesure → privilégier BAR_CHART
- 1 dimension + 1 mesure + ratio → privilégier PIE_CHART
- 2 mesures sans dimension temporelle → privilégier SCATTER_PLOT

### Règles d'optimisation contextuelle
- Si `simplification_requested` : réduire la complexité des visualisations, limiter à 5 séries max
- Si `performance_focused` : pré-agréger, réduire la cardinalité
- Si `mobile_target` : layout stacked, 3 visuals max par page

## Fonctionnalités attendues

1. **Model Mapper** : transformer les entités du graphe sémantique en tables et colonnes normalisées
2. **Logic Encoder** : convertir les formules métier en expressions abstraites avec détection des dépendances
3. **Visualization Planner** : déterminer les types de visualisations optimaux basés sur les données et l'intention
4. **Layout Planner** : organiser la structure du dashboard selon les contraintes utilisateur
5. **Spec Validator** : vérifier la complétude, cohérence et faisabilité de la spécification
6. **Confidence Scorer** : calculer un score de confiance avec recommandations

## Contraintes techniques

- Langage : Python 3.11+
- Framework : Pas de framework spécifique, code modulaire
- Gestion des erreurs : Exception handling avec fallback sur règles heuristiques
- Logging : Logs détaillés pour chaque étape de transformation
- Tests : Cas de test pour chaque type d'intention (conversion, génération, optimisation)

## Format de réponse attendu

Je souhaite recevoir une implémentation complète du Specification Agent avec :

1. **Architecture du module** : structure des classes et leurs responsabilités
2. **Code source complet** : implémentation Python avec typing et docstrings
3. **Configuration** : paramétrage des règles et heuristiques
4. **Exemples d'utilisation** : démonstration avec un cas concret
5. **Tests unitaires** : exemples de tests pour les cas critiques

## Cas d'utilisation de test

### Cas 1 : Conversion Tableau → Power BI avec simplification
- Input : Semantic Graph avec mesure SUM(Sales), dimension Date (hiérarchie Year/Quarter/Month), visualisation bar chart existante
- Contrainte : simplification demandée
- Attendu : Spécification avec visualisation simplifiée (bar chart → line chart pour tendance temporelle)

### Cas 2 : Génération from scratch pour analyse ventes
- Input : Semantic Graph avec tables Sales, Products, Dates
- Intention : analyser les tendances de ventes par catégorie
- Attendu : Spécification avec time series chart et breakdown par catégorie

### Cas 3 : Optimisation de dashboard existant pour mobile
- Input : Semantic Graph avec 8 visualisations complexes
- Contrainte : mobile_target
- Attendu : Spécification avec 3 visuals principaux, layout stacked

Commence par l'architecture générale du module, puis détaille chaque composant avec son implémentation.
```

---

## Prompt Complémentaire pour l'Optimisation (à utiliser après la première réponse)

```
Merci pour l'implémentation de base. Maintenant, j'ai besoin d'optimiser le Specification Agent avec des fonctionnalités avancées :

## 1. Système de règles déclaratives

Implémente un moteur de règles configurable via YAML/JSON pour :
- Les patterns de détection de visualisations
- Les règles de normalisation par type d'outil source (Tableau, Power BI)
- Les transformations spécifiques par intention utilisateur

Exemple de structure :
```yaml
visualization_patterns:
  time_series:
    conditions:
      - field: x_axis
        semantic_type: TEMPORAL
      - field: y_axis
        role: MEASURE
    recommended_types: [LINE_CHART, AREA_CHART]
    confidence_boost: 0.2

tool_normalization:
  tableau:
    measure_aggregations:
      SUM: SUM
      AVG: AVG
      COUNTD: COUNT_DISTINCT
    date_hierarchy: [YEAR, QUARTER, MONTH, DAY]
  
  powerbi:
    measure_aggregations:
      SUM: SUM
      AVERAGE: AVG
      DISTINCTCOUNT: COUNT_DISTINCT
    date_hierarchy: [Year, Quarter, Month, Day]
```

## 2. Gestion de l'incertitude

Ajoute un système de scoring probabiliste :
- Pour chaque décision, stocker le niveau de confiance
- Proposer des alternatives en cas de faible confiance
- Permettre l'intervention humaine sur les points critiques

## 3. Cache sémantique

Implémente un mécanisme de cache pour :
- Éviter de retraiter des structures similaires
- Stocker les correspondances entre patterns récurrents
- Accélérer les transformations répétitives

## 4. Export multi-format

Permettre la spécification d'être exportée en :
- JSON (format standard)
- YAML (lisible par l'homme)
- GraphQL schema (pour API)
- Markdown (documentation)

## 5. Extension points

Prévois des points d'extension pour :
- Ajouter de nouveaux types de visualisations
- Intégrer des règles métier personnalisées
- Connecter des validateurs externes

Donne-moi l'implémentation de ces fonctionnalités avancées en complément du code existant.
```

---

## Prompt pour le Débogage et les Tests

```
J'ai besoin de tester et valider l'implémentation du Specification Agent avec des scénarios complexes. Génère :

## 1. Jeu de données de test

Crée 5 jeux de données de test couvrant :
- Dashboard Tableau complexe avec LOD expressions
- Dashboard Power BI avec DAX time intelligence
- Structure simple CSV pour génération from scratch
- Dashboard avec hiérarchies croisées
- Dashboard avec calculs dépendants circulaires (edge case)

## 2. Tests d'intégration

Pour chaque scénario, génère :
- Le Semantic Graph d'entrée
- La configuration utilisateur (intention + contraintes)
- La spécification abstraite attendue
- Les métriques de validation (compliance score)

## 3. Benchmark

Propose une méthodologie pour benchmarker :
- Temps de génération par taille de dashboard (10, 50, 100, 500 visuals)
- Précision des recommandations de visualisation
- Taux de validation automatique

## 4. Scénarios d'erreur

Gère les cas suivants avec des mécanismes de fallback :
- Incompatibilité de type de données
- Dépendance circulaire non résolvable
- Visualisation non supportée dans l'outil cible
- Manque de données pour la visualisation demandée

Fournis les implémentations des tests unitaires et d'intégration correspondants.
```

---

Ces prompts sont conçus pour être utilisés séquentiellement avec GPT-4.1, permettant un développement itératif et complet du Specification Agent. Chaque prompt peut être ajusté en fonction des réponses obtenues et des besoins spécifiques du projet.