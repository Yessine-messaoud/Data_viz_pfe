# Phase 4 - Transformation

## Objectif

Transformer l'Abstract Spec en un modele cible plus proche du RDL final, avec des datasets, des champs, des calculs et des visuels deja prepares pour la generation paginee.

Cette phase sert de couche d'adaptation entre:
- la spec abstraite issue de la phase 3,
- la structure de rapport attendue par la phase 5,
- les contraintes techniques du moteur RDL.

Cette phase couvre:
- traduction des calculs,
- mapping visuels,
- adaptation de compatibilite cible.

## Entrees

La phase 4 consomme principalement:
- `AbstractSpec`,
- `DataLineageSpec`,
- layouts ou structures de rapport intermediaires lorsqu'ils existent,
- registry de sources et metadonnees issues des phases amont.

## Sortie

La phase 4 produit un modele de transformation exploitable par la phase 5, typiquement:
- datasets RDL prepares pour emission,
- champs et expressions normalises,
- mapping visuel vers les sections cibles,
- erreurs et warnings de transformation,
- traces de lineage de transformation.

## Déroulé détaillé

### 1. Lecture de la spec abstraite
Sous-etapes:
- parcourir les pages, visuels et bindings,
- recuperer les datasets et les objets semantiques transmis,
- identifier les elements a re-ecrire pour la cible RDL.

Resultat attendu:
- une vision complete des visuels et donnees a transformer.

### 2. Traduction des calculs
Sous-etapes:
- convertir les expressions abstraites vers des expressions RDL quand c'est possible,
- harmoniser les noms de mesures et d'agregats,
- conserver les calculs non resolus comme signaux de correction ou de fallback.

Resultat attendu:
- des champs calcules compatibles avec la generation RDL.

### 3. Mapping des datasets
Sous-etapes:
- regrouper les champs par source logique,
- construire les datasets cibles,
- conserver les relations necessaires a la phase 5,
- deduire les champs utilises par visuel.

Resultat attendu:
- des datasets RDL stables et reutilisables.

### 4. Mapping des visuels
Sous-etapes:
- transformer les visuels abstraits en sections exploitables par le generateur RDL,
- preparer la compatibilite avec les controls pagines,
- conserver les informations de mise en page utiles.

Resultat attendu:
- un mapping visuel cible explicite et coherent.

### 5. Normalisation de compatibilite
Sous-etapes:
- ajuster les types d'objets selon les limitations du moteur cible,
- centraliser les corrections de compatibilite,
- supprimer les incoherences qui bloqueraient la phase 5.

Resultat attendu:
- un modele de transformation sans ambiguite bloquante.

## Composants

- `calc_field_translator.py`
- `rdl_dataset_mapper.py`
- `agent/transformation_agent.py`
- `agent/validation_hook.py`
- `agent/lineage_tracker.py`

### Role des composants

- `calc_field_translator.py` : traduit les calculs et normalise les expressions,
- `rdl_dataset_mapper.py` : construit les datasets cibles a partir des sources et champs utilises,
- `agent/transformation_agent.py` : orchestre la transformation deterministe ou hybride,
- `agent/validation_hook.py` : controle la structure intermediaire et remonte les erreurs,
- `agent/lineage_tracker.py` : enregistre les evenements et compteurs de transformation.

## Validation continue

Le hook `agent/validation_hook.py` est actif:

- erreur si `tool_model` invalide,
- erreur si cle `error` presente,
- checks structure `datasets` / `visuals`,
- verification de la presence des elements cibles attendus avant la phase 5,
- warnings si le mapping est incomplet mais recuperable.

## Lineage continu

Le tracker `agent/lineage_tracker.py` capture des evenements de transformation:

- `datasets_count`,
- `visuals_count`,
- `status`,
- timestamp.

Selon le contexte, il peut aussi conserver:
- les objets transformes,
- les champs resolus,
- les avis de compatibilite,
- les corrections appliquees.

## Notes

- le mapping dataset RDL reste base sur le registry phase 0,
- les corrections de compatibilite outil restent centralisees dans `compatibility_manager.py`,
- la phase 4 ne doit pas reinterpréter la semantique brute: elle adapte et normalise seulement,
- les sorties doivent rester stables et traçables pour la phase 5.
