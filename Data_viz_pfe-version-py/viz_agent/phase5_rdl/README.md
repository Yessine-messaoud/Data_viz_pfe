# Phase 5 — Génération et Validation du RDL

## Objectif

Générer le rapport paginé RDL à partir de l'Abstract Spec transformé, des datasets et des layouts, puis valider le fichier produit à plusieurs niveaux avant ecriture finale.

Cette phase est le point de sortie du pipeline:
- elle assemble le XML RDL,
- elle injecte datasources, datasets, parametres et sections,
- elle applique les validations de structure et de compatibilite,
- elle bloque l'ecriture si des erreurs critiques persistent.

## Entrees

La phase 5 consomme en general:
- le modele transforme de phase 4,
- l'Abstract Spec lorsque certaines informations doivent encore etre lues,
- les layouts / pages RDL,
- la configuration de generation et les ressources de connexion.

## Sorties

La phase 5 produit:
- un fichier `.rdl`,
- des erreurs et warnings de validation,
- des corrections automatiques quand elles sont possibles,
- des artefacts de debug ou de diagnostic selon le pipeline.

## Fonctionnalités principales

- generation du fichier RDL XML conforme au standard Microsoft,
- attribution stable des noms de datasets,
- harmonisation des identifiants de mesures et des champs,
- ajout des datasources, datasets et parametres,
- construction des sections du rapport,
- mapping des visuels vers les controles RDL,
- validation multi-niveaux,
- auto-fix deterministe quand les erreurs sont recuperables,
- blocage de l'ecriture si des erreurs critiques persistent.

## Déroulé détaillé

### 1. Préparation du modèle de génération
Sous-etapes:
- lire le modele en entree,
- preparer les references de datasets et de champs,
- identifier les elements requis par le rapport cible.

Resultat attendu:
- un contexte de generation normalise.

### 2. Génération du squelette RDL
Sous-etapes:
- creer la structure XML de base,
- injecter les sections du rapport,
- preparer les zones de donnees, visuels et parametres.

Resultat attendu:
- un RDL squelette complet.

### 3. Injection des données et paramètres
Sous-etapes:
- ajouter les datasources,
- construire ou rattacher les datasets,
- declarer les parametres utiles,
- harmoniser les noms de champs et mesures.

Resultat attendu:
- un RDL structurellement complet cote donnees.

### 4. Mapping visuel
Sous-etapes:
- convertir les visuels abstraits ou transformes en composants RDL,
- affecter les controles aux datasets,
- maintenir la compatibilite de rendu.

Resultat attendu:
- un rapport visuel coherent avec les donnees.

### 5. Validation et auto-fix
Sous-etapes:
- verifier le XML,
- verifier le schema XSD,
- verifier la structure et la semantique,
- corriger automatiquement les erreurs deterministes,
- arreter si les erreurs restent bloquantes apres le nombre maximal de tours.

Resultat attendu:
- un RDL valide ou un ensemble d'erreurs explicites.

## Structure des modules

- `rdl_generator.py` : generation principale du RDL,
- `rdl_validator_pipeline.py` : orchestration de la validation,
- `rdl_auto_fixer.py` : corrections automatiques deterministes,
- `rdl_schema_validator.py` : validation XSD,
- `rdl_structure_validator.py` : validation de structure,
- `rdl_semantic_validator.py` : validation semantique,
- `rdl_xml_validator.py` : validation XML,
- `rdl_visual_mapper.py` : mapping des visuels abstraits vers le RDL.

## Responsabilites du pipeline

- conserver un XML reproductible,
- remonter les erreurs au plus tot,
- ne pas ecraser silencieusement les anomalies,
- bloquer l'ecriture sur erreur critique,
- conserver une trace des correctifs appliques.

## Usage rapide

```python
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
gen = RDLGenerator(llm_client, calc_translator)
rdl_xml = gen.generate(spec, layouts, rdl_pages)
```

## Validation multi-niveaux

La validation s'effectue typiquement dans cet ordre:
1. validation XML,
2. validation XSD RDL,
3. validation structurelle,
4. validation semantique,
5. auto-fix puis revalidation.

Les erreurs bloquees en priorite concernent:
- un XML invalide,
- un schema non conforme,
- des datasets manquants,
- des champs references mais non resolus,
- des parametres incoherents,
- des visuels incompatibles avec la cible.

## Notes de generation

- Le nommage des datasets doit rester stable pour faciliter le debug et la revalidation.
- Les corrections automatiques doivent rester deterministes.
- La phase 5 est la derniere etape avant emission du rapport RDL final.

## Notes

- Le fichier RDL est bloque si des erreurs critiques persistent apres auto-fix.