# Phase 3 - Construction de l'Abstract Spec

## Objectif

La phase 3 transforme le couple `ParsedWorkbook` + `SemanticModel` en une `AbstractSpec` stable, exploitable et directement consommable par les phases de transformation et de génération RDL.

Cette phase sert de pont entre:
- la phase 1, qui produit la structure Tableau enrichie,
- la phase 2, qui produit le modèle sémantique et le lineage logique,
- la phase 4 et la phase 5, qui attendent une structure visuelle, des bindings et des filtres propres.

L'objectif n'est pas de refaire le parsing ni de réinterpréter la source Tableau, mais d'assembler une spécification abstraite cohérente, normalisée et validable.

Cette phase inclut maintenant un `VisualDecisionEngine` et une couche de correction pour éviter les sorties génériques ou ambiguës. Le builder ne fait plus seulement un mapping direct: il choisit un type visuel contractuel, vérifie la compatibilité des axes, corrige les bindings si nécessaire, puis trace les décisions dans le build log.
La correction est deterministe et orientee contrat: elle nettoie les bindings invalides, conserve les elements valides, et remonte les warnings de correction au niveau de l'`AbstractSpec`.

## Rôle de la phase

La phase 3 est responsable de:
- construire les pages du dashboard abstrait,
- mapper chaque worksheet en `VisualSpec`,
- relier les axes et les mesures au modèle sémantique,
- propager les filtres globaux,
- préparer les overrides de type visuel pour les chartes,
- valider les contrats visuels avant la sortie,
- corriger les bindings ou basculer sur un fallback stable si la confidence est trop faible,
- propager les warnings de correction et les issues de validation,
- éliminer les duplications et les incohérences de structure,
- produire un fingerprint de build pour le suivi du pipeline.

## Entrées

La phase consomme principalement:
- `ParsedWorkbook` de phase 1,
- `SemanticModel` de phase 2,
- `DataLineageSpec` produit ou enrichi par la phase 2,
- l'intention pipeline, lorsqu'elle est disponible.

### Ce que la phase 3 lit depuis le workbook

- les worksheets,
- les dashboards,
- les shelves `rows`, `cols`, `marks`,
- les filtres,
- les encodages visuels enrichis,
- les hints sémantiques et la confidence lorsqu'ils sont présents,
- la liaison vers les datasources.

### Ce que la phase 3 lit depuis la phase 1 enrichie

- `raw_mark_type`
- `visual_encoding`
- `semantic_hints`
- `confidence`
- `enriched_lineage`
- `validation_warnings`

### Ce que la phase 3 lit depuis le modèle sémantique

- les entités et leurs colonnes,
- les rôles `measure` / `dimension`,
- les mesures sémantiques,
- les collisions de noms,
- les informations utiles au binding des axes.

## Sortie

La sortie principale est une `AbstractSpec` contenant:
- `dashboard_spec`: structure des pages, visuels, filtres et thème,
- `semantic_model`: modèle sémantique transmis tel quel,
- `data_lineage`: lineage transmis tel quel,
- `rdl_datasets`: initialement vide puis rempli par la phase 4,
- `build_log`: journal de construction,
- `warnings`: avertissements de build.

## Architecture interne

### `abstract_spec_builder.py`

Le builder est le point d'entrée principal de la phase.

Rôle de `DashboardSpecFactory`:
- indexer les rôles de colonnes à partir du `SemanticModel`,
- convertir les worksheets en `VisualSpec`,
- construire les `DataBinding`,
- gérer le `visual_type_override`,
- appeler le `VisualDecisionEngine`,
- appliquer la correction si le contrat visuel n'est pas respecté,
- grouper les worksheets en pages si les dashboards Tableau ne fournissent pas de découpage exploitable,
- dédupliquer les filtres globaux.

Rôle de `AbstractSpecBuilder`:
- encapsuler l'assemblage final,
- générer l'`id`, la version et le `source_fingerprint`,
- injecter le `build_log` initial.

### `specification_agent.py`

Point d'orchestration ou d'extension pour les stratégies de spécification plus avancées.

### `components/`

Répertoire des briques de planification, d'encodage logique, de validation et d'export lorsque le pipeline passe par des variantes de spécification plus évoluées.

### `visual_contracts.py`

Définit les contrats visuels stricts et les règles de validation métier pour les types suivants:
- `bar`
- `line`
- `pie`
- `treemap`
- `scatter`
- `kpi`
- `table`
- `map`
- `gantt`

### `visual_decision_engine.py`

Résout le type visuel final à partir de:
- la phase 1 enrichie,
- le `mark_type` brut,
- le `VisualEncoding`,
- la confidence,
- le modèle sémantique.

Le moteur:
- privilégie les types métiers explicites,
- applique un fallback si la confidence est faible,
- corrige les axes et les bindings pour rester contractuel,
- conserve les warnings et corrections dans le retour.

Le moteur s'appuie sur des regles visuelles explicites, notamment:
- `bar`: `x` dimension, `y` mesure, `color` dimension optionnelle, `size` interdit, `detail` dimension optionnelle
- `treemap`: `group` dimension obligatoire, `size` mesure obligatoire, `color` dimension optionnelle, pas de `x/y`

### `spec_correction.py`

Applique une correction conservatrice après la décision initiale:
- normalise les visuels génériques,
- répare les bindings incomplets,
- évite les downgrades inutiles pour les visuels déjà spécifiques,
- retourne un état corrigé avec issues et corrections,
- ajoute les warnings de correction au payload final pour faciliter la génération RDL.

## Déroulé détaillé

### 1. Indexation des rôles

La phase commence par construire un index des rôles sémantiques.

Elle parcourt les entités du `SemanticModel` et résout:
- les colonnes `measure`,
- les colonnes `dimension`,
- les collisions de nom entre tables.

Résultat:
- une vue rapide des rôles par `(table, colonne)`,
- une vue secondaire par nom de colonne pour les cas ambigus.

### 2. Construction des bindings

Chaque worksheet est convertie en `DataBinding`.

La logique actuelle associe:
- `cols` -> axe `x`,
- `rows` -> axe `y`,
- encodages de marks explicites -> `color/size/detail` quand ils existent,
- fallback positionnel uniquement pour les cas Tableau qui n'exposent pas les canaux explicitement.

Les références qui pointent vers des mesures sémantiques sont converties en `MeasureRef`, sinon en `ColumnRef`.

### 3. Résolution du type visuel

La phase 3 utilise [visual_type_mapper.py](../phase1_parser/visual_type_mapper.py) pour obtenir un mapping explicite:
- type logique,
- type RDL,
- override de série chart si nécessaire.

La résolution prend en compte:
- le `mark_type` Tableau,
- le `VisualEncoding` enrichi,
- le nom de worksheet dans les cas ambigus,
- les cas `Automatic`.

Le `VisualDecisionEngine` intervient ensuite pour confirmer ou corriger ce mapping en fonction du contrat visuel attendu. Si le workbook est trop ambigu ou trop pauvre, le moteur peut choisir un fallback stable comme `table`, `kpi` ou `map`, puis la correction vient stabiliser le binding avant la validation finale.

### 4. Construction des pages

Si le workbook fournit des dashboards avec des worksheets explicites, la phase 3 conserve ce découpage.

Sinon, elle applique un regroupement déterministe par nom de worksheet via les préfixes métier connus, afin de produire des pages plus utiles pour le dashboard final.

Résultat:
- une liste de `DashboardPage`,
- chaque page contient ses `VisualSpec`.

### 5. Propagation des filtres

Les filtres du workbook sont dédupliqués et transférés dans `DashboardSpec.global_filters`.

La déduplication repose sur:
- le champ,
- l'opérateur,
- la valeur.

### 6. Génération du fingerprint

Le builder produit un fingerprint SHA-256 basé sur:
- le nombre de worksheets,
- le nombre de dashboards,
- le nombre de tables lineage,
- le nombre de joins lineage.

Ce fingerprint sert à tracer la stabilité de la spécification dans le pipeline.

## Modèle de données

### `DashboardSpec`

Contient:
- `pages`
- `global_filters`
- `theme`

### `DashboardPage`

Contient:
- `id`
- `name`
- `visuals`

### `VisualSpec`

Contient:
- `id`
- `source_worksheet`
- `type` logique,
- `rdl_type` cible,
- `title`
- `position`
- `data_binding`

### `DataBinding`

Contient:
- `axes`
- `measures`
- `filters`
- `visual_type_override`
- `pending_translations`

## Validation de la phase 3

La phase 3 ne valide pas tout de manière bloquante, mais elle prépare les données pour les validateurs suivants.

Les points contrôlés par la phase 3b sont notamment:
- tables inconnues,
- colonnes brutes non normalisées,
- datasets RDL vides,
- table de faits incohérente,
- pages dupliquées,
- axes vides,
- types de visuels non standards,
- contrats visuels invalides ou incomplets,
- tables fantômes,
- score global de validation.

Le principe est simple:
- la phase 3 construit,
- la phase 3b filtre et signale,
- la phase 4 transforme,
- la phase 5 génère le RDL.

## Compatibilité avec les autres phases

### Avec la phase 1

La phase 3 exploite:
- `mark_type` résolu,
- `raw_mark_type`,
- `visual_encoding`,
- `semantic_hints`,
- `confidence`,
- `enriched_lineage`.

La qualité de cette phase dépend directement de l'enrichissement phase 1. Plus les encodages et les hints sont riches, plus le moteur visuel peut éviter les fallbacks.

### Avec la phase 2

La phase 3 exploite:
- les rôles sémantiques,
- les mesures,
- la table de faits,
- le lineage.

### Avec la phase 4

La phase 4 récupère l'`AbstractSpec` pour produire le modèle outil et les artefacts intermédiaires.

### Avec la phase 5

La phase 5 consomme la structure visuelle pour générer le RDL concret, les layouts et les datasets.

## Usage rapide

```python
from viz_agent.models.abstract_spec import DataLineageSpec, ParsedWorkbook, SemanticModel
from viz_agent.phase3_spec.abstract_spec_builder import AbstractSpecBuilder

spec = AbstractSpecBuilder.build(
	workbook=parsed_workbook,
	intent={"type": "conversion"},
	semantic_model=semantic_model,
	lineage=DataLineageSpec(),
)
```

## Sorties typiques

Après exécution, on obtient généralement:
- un `DashboardSpec` avec une ou plusieurs pages,
- des visuels logiques `bar`, `line`, `pie`, `treemap`, `map`, `kpi`, `table`,
- des `rdl_type` explicites,
- des `build_log` détaillant les décisions et corrections,
- des filtres globaux dédupliqués,
- un `AbstractSpec` sérialisable en JSON.

## Limitations connues

- la phase 3 reste dépendante de la qualité du parsing phase 1,
- les worksheets ambiguës peuvent nécessiter une validation complémentaire,
- les collisions de colonnes sont résolues par heuristique sémantique,
- certains cas très pauvres en signaux finissent encore en fallback `table`,
- les mappings ultra complexes restent à stabiliser via la phase 4 et la phase 5.

## Fichiers associés

- [abstract_spec_builder.py](abstract_spec_builder.py)
- [visual_contracts.py](visual_contracts.py)
- [visual_decision_engine.py](visual_decision_engine.py)
- [spec_correction.py](spec_correction.py)
- [../phase1_parser/visual_type_mapper.py](../phase1_parser/visual_type_mapper.py)
- [../phase3b_validator/abstract_spec_validator.py](../phase3b_validator/abstract_spec_validator.py)

## Note

L'Abstract Spec doit toujours être considéré comme la structure contractuelle entre l'analyse sémantique et la génération RDL. Elle ne remplace ni le workbook Tableau, ni le modèle sémantique, mais les normalise pour les phases aval.