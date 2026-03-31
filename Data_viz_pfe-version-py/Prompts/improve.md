---
# Plan de fusion phase0_data → phase0_extraction

1. Garder la structure phase0_extraction (adapters, readers, normalization, models, etc.).
2. Migrer/adapter les modules utiles de phase0_data :
  - CSVLoader → adapters/readers
  - HyperExtractor → adapters/readers
  - DBConnector → adapters/readers
  - DataSourceRegistry → registry/metadata_catalog.py (ou à intégrer dans pipeline)
3. Centraliser la logique d’extraction universelle dans pipeline.py (mode live, extract, rdl, toutes colonnes/tables, annotation is_used_in_dashboard).
4. Adapter les appels du pipeline pour utiliser phase0_extraction.
5. Supprimer phase0_data une fois la migration validée.

Ce plan garantit la compatibilité, la clarté et la normalisation Pydantic.
Je vais analyser le README en profondeur pour faire un état des lieux précis du projet.---

## Synthèse de l'état présent

**Ce qui tourne réellement** : le pipeline de bout en bout fonctionne pour le cas nominal — un `.twbx` Tableau avec extraction Hyper → AbstractSpec → RDL. Les phases 1, 3 et 6 sont les plus matures.

**Ce qui est cassé ou partiel** :

La Phase 4 est le point chaud du moment. Les 3 bugs RDL qu'on a disséqués dans cette session (`<Y>=0`, grouping manquant, types String) en sont la preuve — le générateur produit du XML structurellement invalide pour SSRS dans certains cas. Le correctif `rdl_datasets` est la priorité immédiate car c'est la source de vérité qui alimente le générateur.

La Phase 0 est fonctionnelle mais sous-dimensionnée par rapport à votre objectif drag & drop. Elle extrait ce qui est utilisé dans les visuels, pas tout le schéma de la source. C'est exactement le chantier du prompt raffiné.

La Phase 2 (Semantic Agent) a une fragilité structurelle : le nommage des mesures est bilingue (technique EN vs label FR) sans couche de résolution. Tant que ce mapping n'est pas formalisé dans le modèle, des bugs d'incohérence réapparaîtront à chaque nouvelle mesure calculée.

**Le saut Phase 5** est un signal d'architecture — soit une phase a été absorbée dans Phase 6, soit la numérotation cache une fonctionnalité planifiée (validation inter-outils ? réconciliation ?) qui n'a pas encore été implémentée.

---

## Échecs et points faibles par phase

### Phase 0 — Extraction
- Extraction partielle : seules les colonnes utilisées dans les visuels sont extraites, le schéma complet n’est pas couvert.
- Pas de support du mode Live (connexion SQL directe non gérée).
- Absence de MetadataModel normalisé (Pydantic).
- Refactoring planifié mais non réalisé.

### Phase 1 — Parsing Workbook
- Fonctionnelle et documentée, mais la documentation (README_PHASE1) n’est pas référencée, ce qui limite la compréhension externe.

### Phase 2 — Semantic Agent
- Incohérence de nommage des mesures (bilingue technique EN vs label FR) sans couche de résolution formalisée.
- Dépendance unique à Mistral (pas de fallback LLM alternatif).
- Neo4j optionnel mais non testé en production.

### Phase 3 — Specification Agent
- AbstractSpec v2 produite et validée, mais axes.y du dashboard_spec non aligné sur le semantic_model.
- Validateur Phase 3b présent mais portée non documentée.

### Phase 4 — Transformation Agent
- Mapping RDL implémenté mais 3 bugs critiques identifiés :
  - rdl_type String sur mesures numériques (non corrigé dans rdl_datasets)
  - ChartCategoryHierarchy sans Group (graphique vide)
  - <Y>=0 dans certains cas
- PBIX/TWBX non encore implémentés.

### Phase 6 — Export Agent
- Artefacts multiples produits, architecture cohérente.
- Bug connu : désérialisation chart dans Report Builder (cas edge).
- Phase 5 absente dans le pipeline (saut Phase 4 → Phase 6).

### Risques transverses
- Dépendance unique Mistral — aucun fallback LLM configuré.
- SQL Server local uniquement (localhost\SQLEXPRESS) — non portable cloud.
- Tests présents mais couverture non mesurée — pas de CI/CD mentionné.
- Credentials SQL dans la connection string — pas de gestion secrets (vault).

---

## Axes d’amélioration par phase

### Phase 0 — Extraction
- Standardiser la sortie avec un schéma Pydantic strict (MetadataModel).
- Extraire toutes les colonnes/tables, annoter is_used_in_dashboard.
- Ajouter un log de correction pour chaque auto-fix (ex : typage, nulls).
- Intégrer la capture de lineage et de décision (méthode, fallback).

### Phase 1 — Parsing
- Valider la correspondance entre colonnes extraites et utilisées dans les visuels.
- Tracer les fallback (heuristique, LLM) et leur raison/confidence.
- Standardiser l’artefact de parsing (structure + metadata).

### Phase 2 — Semantic
- Vérifier la cohérence des types et des noms entre semantic_model et parsing.
- Ajouter un score de confiance global et tracer les décisions LLM/règle.
- Enrichir le lineage avec les choix de mapping et de résolution d’ambiguïté.

### Phase 3 — Specification
- S’assurer que l’AbstractSpec est alignée sur le semantic_model (axes, mesures).
- Ajouter une validation croisée (GlobalValidationAgent) avant export.
- Standardiser la sortie (data + metadata).

### Phase 4 — Transformation
- Vérifier la compatibilité des types et des expressions avec la spec.
- Tracer toutes les corrections automatiques (auto-fix, cast, fallback).
- Ajouter un log détaillé des étapes de transformation.

### Phase 5 — RDL Generation/Validation
- Rendre la validation obligatoire (jamais de saut de phase).
- Centraliser les auto-fix et corrections dans un CorrectionLogger.
- Standardiser le rapport de validation (score, issues, corrections).

### Phase 6 — Export/Lineage
- Étendre le lineage pour inclure toutes les décisions, corrections et transformations.
- Exporter tous les artefacts intermédiaires avec metadata standardisée.

### Global
- Ajouter un GlobalValidationAgent pour la validation croisée.
- Intégrer une couche d’observabilité (validation, lineage, monitoring, correction).
- Uniformiser tous les artefacts produits (data + metadata).
- Documenter et tracer tous les fallback, corrections et décisions.

---

## Points de rupture ou de contournement

- Saut de la phase 5 (validation RDL) dans certains flows : risque de propagation d’erreurs non détectées.
- Corrections automatiques (auto-fix) appliquées sans log centralisé ni validation croisée.
- Fallbacks LLM/heuristique non toujours tracés dans le lineage ou la correction.
- Validation locale (par phase) mais peu de validation globale (cross-phase).
- Documentation incomplète des artefacts intermédiaires (README, lineage, logs).
- Standardisation partielle des artefacts : certains outputs n’ont pas de metadata unifiée.
- Gestion des erreurs parfois silencieuse (corrections appliquées sans notification explicite).

**Recommandations** :
- Rendre la validation de phase 5 obligatoire et bloquante.
- Centraliser tous les logs de correction et fallback (CorrectionLogger, DecisionTracker).
- Étendre le lineage pour inclure toutes les décisions et corrections.
- Ajouter un GlobalValidationAgent pour la validation croisée.
- Uniformiser la structure de tous les artefacts produits.

---

## Synthèse des recommandations d’amélioration

1. **Validation obligatoire et globale**
   - Toujours exécuter la phase 5 (validation RDL), sans exception.
   - Ajouter un GlobalValidationAgent pour vérifier la cohérence entre tous les artefacts.

2. **Standardisation des artefacts**
   - Uniformiser la structure de sortie de chaque phase (data + metadata).
   - Documenter et exporter tous les artefacts intermédiaires.

3. **Observabilité et traçabilité**
   - Intégrer une couche d’observabilité : validation continue, lineage enrichi, monitoring, correction log.
   - Tracer toutes les décisions (LLM, heuristique, auto-fix) et corrections appliquées.

4. **Correction et auto-fix explicites**
   - Centraliser tous les logs de correction dans un CorrectionLogger.
   - Notifier et documenter chaque correction ou fallback appliqué.

5. **Documentation et tests**
   - Compléter la documentation des artefacts, du flow et des logs.
   - Ajouter des tests d’intégration pour valider la robustesse du pipeline sur des cas limites.

**Bénéfices attendus** : pipeline plus robuste, traçable, auto-corrigeant, et prêt pour l’industrialisation BI agentique.