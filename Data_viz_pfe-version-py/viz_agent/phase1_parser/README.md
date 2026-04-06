# Phase 1 - Parsing du Workbook Tableau

## Objectif

Transformer un workbook Tableau brut en une structure `ParsedWorkbook` stable, lisible et exploitable par les phases suivantes.

Cette phase prend en entrée:
- `.twbx` : archive Tableau packagee
- `.twb` : document XML Tableau

Cette phase produit:
- un workbook parse avec worksheets, dashboards, datasources, champs calcules, parametres et filtres,
- une structure compatible avec la couche semantique,
- un flux de validation et de lineage continu pendant le parsing.

Le parsing ajoute aussi un enrichissement pre-semantique deterministe pour capturer les encodages visuels, les indices de role des colonnes, les scores de confiance et le lineage colonne -> visuel.
Les encodages de marks sont maintenant resolus de facon explicite via `mark_encodings` pour eviter les faux positifs sur `color` quand seul `size` ou `detail` est present.

## Contrat de sortie

Le `ParsedWorkbook` conserve les champs historiques du parser, et expose maintenant aussi des donnees enrichies pour les phases suivantes:

- `visual_encoding`: encodage structurel `x/y/color/size/detail` par worksheet
- `mark_encodings`: correspondance explicite des canaux Tableau (`color`, `size`, `detail`) vers les colonnes source
- `semantic_hints`: indices de role et d'agregation par colonne
- `confidence`: scores `visual`, `encoding`, `datasource_linkage`, `overall` par worksheet
- `enriched_lineage`: traces colonne -> visuel
- `validation_warnings`: avertissements non bloquants issus de l'enrichissement

## Fonctionnalites principales

- chargement XML Tableau (`.twb` et `.twbx`)
- parsing des worksheets et des dashboards
- parsing des datasources et des connexions
- extraction des champs calcules
- extraction des parametres et filtres
- extraction des palettes
- mapping explicite des types de visualisations Tableau vers les types RDL
- enrichissement pre-semantique des worksheets
- validation structurelle continue
- capture du lineage d'execution

## Déroulé détaillé

### 1. Chargement du workbook
Sous-étapes:
- ouvrir le fichier Tableau fourni en entree,
- identifier si l'entrée est une archive `.twbx` ou un XML `.twb`,
- initialiser la registry des sources de donnees,
- preparer le contexte de parsing sans modifier le fichier source.

Résultat attendu:
- une entrée normalisée pour le parseur,
- une base d’extraction commune pour les formats supportés.

### 2. Lecture et extraction XML
Sous-étapes:
- parser le XML avec tolerance de recouvrement,
- naviguer dans les noeuds Tableau pertinents,
- récupérer les sections `worksheets`, `dashboards`, `datasources`, `calculated fields`, `parameters`, `filters`, `color palettes`,
- ignorer les artefacts non nécessaires au modèle.

Résultat attendu:
- une vue structurée des objets Tableau contenus dans le workbook.

### 3. Parsing des datasources
Sous-étapes:
- extraire les sources de données embarquées ou liées,
- récupérer les colonnes et leurs attributs,
- identifier les types de colonnes,
- associer les sources aux tables/registres en entrée,
- conserver les métadonnées techniques utiles pour les phases suivantes.

Résultat attendu:
- des datasources prêtes à être normalisées,
- une base de colonnes et connexions réutilisable par la phase 0 et la phase 2.

### 4. Parsing des worksheets
Sous-étapes:
- lire les feuilles du workbook,
- extraire le nom de la worksheet,
- détecter le type de marque (`mark_type`),
- capturer les champs placés sur les shelves (`rows`, `columns`, `marks`),
- associer chaque champ à son datasource d’origine si possible.

Résultat attendu:
- une liste de worksheets décrivant les visuels Tableau,
- les informations minimales nécessaires au mapping vers le modèle logique.

### 4b. Encodage visuel structuré
Sous-étapes:
- transformer `columns` en `x`,
- transformer `rows` en `y`,
- transformer les encodages `color`, `size`, `detail` via les canaux explicites du workbook,
- conserver une représentation stable et sérialisable par worksheet.

Résultat attendu:
- un objet `VisualEncoding` exploitable par la phase semantique,
- une base pour la detection des types automatiques et des ambiguïtés Tableau.

### 5. Parsing des dashboards
Sous-étapes:
- identifier les dashboards,
- extraire les pages et les zones de feuille,
- associer les worksheets visibles à chaque dashboard,
- conserver l’ordre et la structure des pages lorsqu’ils sont disponibles.

Résultat attendu:
- un mapping clair dashboard -> pages -> worksheets,
- la base de la future spécification visuelle et de l’export RDL.

### 6. Extraction des champs calculés, filtres et paramètres
Sous-étapes:
- lire les champs calculés Tableau,
- récupérer les expressions associées,
- extraire les filtres globaux et locaux,
- capturer les paramètres de rapport,
- conserver ces éléments dans le `ParsedWorkbook` pour les phases suivantes.

Résultat attendu:
- une vision plus complète du comportement analytique du workbook,
- des signaux utiles pour la phase semantique et la génération RDL.

### 7. Normalisation du workbook parse
Sous-étapes:
- convertir les objets extraits en modèles Pydantic,
- harmoniser les noms et champs,
- standardiser les types et les listes vides,
- produire un `ParsedWorkbook` cohérent et sérialisable.

Résultat attendu:
- une structure unique, stable et compatible pipeline,
- une sortie directement consommable par les couches semantique et spec.

### 8. Mapping des types de visualisation
Sous-étapes:
- mapper les `mark_type` Tableau vers les types logiques,
- préparer la conversion Tableau -> logique RDL,
- conserver une correspondance explicite entre worksheet et visuel final.

Résultat attendu:
- un type de visuel exploitable pour la phase spec,
- une base homogène pour la génération RDL.

Règles principales:
- aucun `rdl_type` générique `chart` n'est émis par le parser enrichi,
- les types reconnus sont mappés de façon explicite vers `ColumnChart`, `LineChart`, `PieChart`, `TreeMap`, `Textbox`, `Map` ou `Tablix`,
- les types inconnus déclenchent un avertissement non bloquant et retombent sur un fallback stable.

### 8b. Gestion des marques ambiguës
Sous-étapes:
- traiter `mark_type = Automatic` de manière déterministe,
- utiliser la structure des encodages pour résoudre le type,
- privilégier la lecture sémantique des shelves plutôt qu'un fallback aveugle.

Heuristiques principales:
- `1 dimension + 1 mesure` -> `bar`,
- `1 mesure` -> `kpi`,
- `plusieurs mesures` -> `line`,
- `color + size` sans axes -> `treemap`.

### 9. Validation continue
Sous-étapes:
- vérifier la présence des clés structurelles attendues,
- signaler les dashboards absents ou invalides,
- signaler les types non conformes sur `visuals` et `bindings`,
- remonter des warnings sans stopper le pipeline lorsque cela est récupérable.

Résultat attendu:
- un parser robuste,
- des anomalies visibles tôt,
- un flux de correction plus simple dans les phases amont.

### 10. Capture du lineage
Sous-étapes:
- enregistrer des événements horodatés pendant l’exécution,
- tracer les étapes de parsing significatives,
- conserver les informations utiles au diagnostic et au debug.

Résultat attendu:
- un historique léger de l’exécution,
- une meilleure observabilité de la phase 1.

## Structure

- `tableau_parser.py`: parser principal
- `dashboard_zone_mapper.py`: extraction des worksheets presentes dans les dashboards
- `column_decoder.py`: decodage des references colonnes
- `visual_type_mapper.py`: mapping type visual Tableau -> type RDL
- `pre_semantic_enricher.py`: enrichissement deterministic des worksheets et du workbook
- `agent/`: couche agentique (deterministic/heuristic/llm + hooks validation/lineage)

## Donnees enrichies

Le `ParsedWorkbook` expose maintenant:

- `visual_encoding`: encodage structurel `x/y/color/size/detail` par worksheet
- `mark_encodings`: mapping explicite des encodages Tableau quand ils existent
- `semantic_hints`: indices de role et d'agregation par colonne
- `confidence`: scores `visual`, `encoding`, `datasource_linkage`, `overall` par worksheet
- `enriched_lineage`: traces colonne -> visuel

Chaque worksheet peut aussi porter directement:

- `raw_mark_type`: classe Tableau brute avant résolution
- `visual_encoding`: objet `VisualEncoding`
- `semantic_hints`: liste de `SemanticHint`
- `confidence`: objet `ConfidenceScore`
- `enriched_lineage`: liste de `EnrichedLineageEntry`
- `validation_warnings`: avertissements locaux non bloquants

## Validation continue

Le hook `agent/validation_hook.py` est actif et ajoute des issues structurelles:

- cle `dashboards` absente ou invalide
- types invalides sur `visuals` / `bindings`
- warning si zero dashboard
- warning si visual sans mesure
- warning si encodage vide ou incomplet
- warning si type visuel non resolu

## Exemple d'usage

```python
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry
from viz_agent.phase1_parser.tableau_parser import TableauParser

parser = TableauParser()
parsed = parser.parse("workbook.twbx", DataSourceRegistry())

first = parsed.worksheets[0]
print(first.visual_encoding.model_dump())
print(first.semantic_hints)
print(first.confidence.model_dump())
print(first.enriched_lineage)
```

## Lineage continu

Le hook `agent/lineage_hook.py` capture des evenements horodates par execution.

## Usage

```python
from viz_agent.phase1_parser.tableau_parser import TableauParser
from viz_agent.phase0_data.data_source_registry import DataSourceRegistry

parser = TableauParser()
parsed = parser.parse("workbook.twb", DataSourceRegistry())
print(parsed.worksheets)
print(parsed.dashboards)
```

## Limites actuelles

- parsing `.rdl` non implemente dans cette phase
- `agent/deterministic_parser.py` reste un scaffold pour la voie agentique alternative
- certaines structures Tableau complexes peuvent nécessiter le fallback heuristique ou LLM
