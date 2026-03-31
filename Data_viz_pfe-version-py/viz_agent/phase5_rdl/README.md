# Phase 5 — Génération et Validation du RDL

## Objectif
Générer le rapport paginé RDL à partir de l’Abstract Spec, des datasets et des layouts, puis valider le fichier généré à plusieurs niveaux.

## Fonctionnalités principales
- **Génération du fichier RDL** (XML) conforme au standard Microsoft
- **Attribution des noms de datasets**
- **Harmonisation des identifiants de mesures**
- **Ajout des datasources, datasets, paramètres**
- **Construction des sections du rapport**
- **Validation multi-niveaux** :
  - Syntaxe XML
  - Schéma XSD RDL
  - Structure et sémantique (datasets, champs, paramètres)
- **Auto-fix** des erreurs déterministes (max 3 tours)
- **Blocage de l’écriture si erreurs persistantes**

## Structure des modules
- `rdl_generator.py` : Génération principale du RDL
- `rdl_validator_pipeline.py` : Pipeline de validation
- `rdl_auto_fixer.py` : Correction automatique
- `rdl_schema_validator.py`, `rdl_structure_validator.py`, `rdl_semantic_validator.py`, `rdl_xml_validator.py` : Validations spécialisées
- `rdl_visual_mapper.py` : Mapping des visuels

## Usage rapide
```python
from viz_agent.phase5_rdl.rdl_generator import RDLGenerator
gen = RDLGenerator(llm_client, calc_translator)
rdl_xml = gen.generate(spec, layouts, rdl_pages)
```

## Notes
- Le fichier RDL est bloqué si des erreurs critiques persistent après auto-fix.