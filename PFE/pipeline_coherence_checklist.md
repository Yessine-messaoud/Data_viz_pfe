# Checklist de Cohérence Pipeline (Concept vs Existant)

Date de démarrage validation: 2026-04-01
Référence concept: `PFE/pipeline_description.md`

## Légende
- `[x]` Validé conforme
- `[~]` Partiellement conforme
- `[ ]` Non conforme / à corriger

## P0 (bloquant exécution)

- [x] `P0-01` Imports phase 0 cohérents (`phase0_data` vs `phase0_extraction`)
  - Attendu: le pipeline runtime importe uniquement des modules existants.
  - Action: ajout d'une couche de compatibilité `viz_agent/phase0_data/` (wrappers vers `phase0_extraction`).
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_data/__init__.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_data/csv_loader.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_data/hyper_extractor.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_data/data_source_registry.py`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_main.py Data_viz_pfe-version-py/viz_agent/tests/test_phase0.py -q`
  - Résultat: `4 passed`

- [x] `P0-02` Cohérence orchestrateur <-> factory (`get_agent` vs `create`)
  - Attendu: l’orchestrateur doit appeler une API réellement exposée par `AgentFactory`.
  - Action: ajout de `get_agent(...)` dans `AgentFactory` + alias legacy `phase5_rdl`.
  - Action: ajout d'une méthode `run(...)` de compatibilité dans `ExportAgent`.
  - Réf: `Data_viz_pfe-version-py/viz_agent/orchestrator/agentic_orchestrator.py:98`, `:133`
  - Réf: `Data_viz_pfe-version-py/viz_agent/orchestrator/agent_factory.py:41`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase5_rdl/agent/export_agent.py`

- [x] `P0-03` Cohérence modèle `source_type` en phase 0
  - Attendu: les valeurs assignées dans le pipeline doivent respecter l’énumération du modèle.
  - Action: extension de l'énumération avec `"csv"`.
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_extraction/pipeline.py:42`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_extraction/models.py:52`

## P1 (fonctionnel agentique)

- [~] `P1-01` Phases 0→6 présentes et enchaînées
  - Attendu: pipeline modulaire couvrant extraction, parsing, sémantique, spec, transformation, génération/validation, lineage.
  - Preuve: phases appelées dans `viz_agent/main.py`.
  - Réf: `Data_viz_pfe-version-py/viz_agent/main.py:311` à `:426`
  - Note: conforme sur la structure globale; reste à homogénéiser l'orchestration agentique complète vs pipeline runtime direct.

- [~] `P1-02` Initialisation orientée intention (conversation + intent detection + pipeline dynamique)
  - Attendu: intention structurée issue de la requête utilisateur, orchestration dynamique.
  - Action: remplacement de l'intent statique par un intent structuré construit dynamiquement.
  - Détails: détection automatique du type d'intent + override CLI (`--intent-type`) + contraintes JSON (`--intent-constraints`) + cible pipeline.
  - Réf: `Data_viz_pfe-version-py/viz_agent/main.py:61`
  - Réf: `Data_viz_pfe-version-py/viz_agent/main.py:365`
  - Réf: `Data_viz_pfe-version-py/viz_agent/main.py:479`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_main.py -q`
  - Résultat: `2 passed`
  - Reste à faire: branchement d'un vrai flux conversation/ambiguïté + orchestration adaptative réellement pilotée par cet intent.

- [~] `P1-03` Support parsing multi-artefacts conceptés (`.twb/.twbx/.rdl`)
  - Attendu: couverture réelle des formats annoncés.
  - Action: support runtime `.twb` ajouté en plus de `.twbx`.
  - Détails: validation d'entrée `.twb/.twbx`, chargement XML direct `.twb`, extraction phase 0 compatible `.twb` (registry vide).
  - Réf: `Data_viz_pfe-version-py/viz_agent/main.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase1_parser/tableau_parser.py`
  - Action complémentaire: implémentation parsing déterministe `.rdl` + `.twb/.twbx` dans l'agent de phase 1.
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase1_parser/agent/deterministic_parser.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase1_parser/agent/parsing_agent.py`
  - Tests ajoutés: `Data_viz_pfe-version-py/viz_agent/tests/test_phase1_deterministic_parser.py`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_phase1_deterministic_parser.py Data_viz_pfe-version-py/viz_agent/tests/test_main.py -q`
  - Résultat: `5 passed`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_main.py Data_viz_pfe-version-py/viz_agent/tests/test_phase0.py -q`
  - Résultat: `5 passed`
  - Reste à faire: brancher le flux runtime principal (`main.py`) sur le chemin `.rdl` end-to-end (aujourd'hui il reste centré Tableau).

- [~] `P1-04` Validation transversale continue (chaque phase)
  - Attendu: hooks de validation réellement implémentés et actifs.
  - Action: implémentation des hooks phase1/phase2/phase4 (règles locales + délégation optionnelle `validation_agent`).
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase1_parser/agent/validation_hook.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase2_semantic/agent/validation_hook.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase4_transform/agent/validation_hook.py`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_validation_hooks.py Data_viz_pfe-version-py/viz_agent/tests/test_main.py -q`
  - Résultat: `7 passed`
  - Reste à faire: homogénéiser la validation continue sur toutes les phases (0/3/5/6) avec un contrat global unique.

- [~] `P1-05` Lineage transversal continu (chaque phase)
  - Attendu: capture lineage active durant le pipeline, pas seulement export final.
  - Action: implémentation de la capture lineage dans les hooks phase1/phase2/phase4 (événements horodatés + extension via `lineage_agent`).
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase1_parser/agent/lineage_hook.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase2_semantic/agent/lineage_hook.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase4_transform/agent/lineage_tracker.py`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_lineage_hooks.py Data_viz_pfe-version-py/viz_agent/tests/test_validation_hooks.py Data_viz_pfe-version-py/viz_agent/tests/test_main.py -q`
  - Résultat: `11 passed`
  - Reste à faire: unifier le lineage de toutes les phases dans un graphe continu central.

- [~] `P1-06` Boucle self-healing opérationnelle
  - Attendu: détection -> correction ciblée -> ré-exécution partielle réellement active.
  - Action: refactor de l'orchestrateur avec exécution step-by-step, détection d'échec validation, correction ciblée (`auto_fix`) et ré-exécution partielle du step fautif.
  - Action: intégration des stratégies de reprise via `ErrorHandler` (retry/fallback/skip/abort).
  - Réf: `Data_viz_pfe-version-py/viz_agent/orchestrator/agentic_orchestrator.py`
  - Tests ajoutés: `Data_viz_pfe-version-py/viz_agent/tests/test_orchestrator_self_healing.py`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_orchestrator_self_healing.py Data_viz_pfe-version-py/viz_agent/tests/test_lineage_hooks.py Data_viz_pfe-version-py/viz_agent/tests/test_validation_hooks.py Data_viz_pfe-version-py/viz_agent/tests/test_main.py -q`
  - Résultat: `13 passed`
  - Reste à faire: brancher des stratégies de correction métier plus fines par phase (au-delà de l'heuristique retry).

## P2 (complétude fonctionnelle)

- [~] `P2-01` Détection des relations phase 0 (FK + heuristiques)
  - Attendu: relations réellement détectées et intégrées au modèle.
  - Action: implémentation de `detect_from_heuristics(...)` et `detect_from_fk(...)`.
  - Action: branchement effectif dans `phase0_extraction/pipeline.py` avec déduplication des relations.
  - Action: normalisation alignée (`source_type` / `source_path`) pour éviter les incohérences de modèle.
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_extraction/relationship_detection/relationship_detector.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_extraction/pipeline.py`
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase0_extraction/normalization/metadata_normalizer.py`
  - Validation exécutée: `python -m py_compile ...relationship_detector.py ...metadata_normalizer.py ...pipeline.py`
  - Validation exécutée: `python -m pytest Data_viz_pfe-version-py/viz_agent/tests/test_main.py -q`
  - Résultat: compilation OK + `3 passed`
  - Reste à faire: tests dédiés relations sur datasets SQL réels et extraction FK multi-SGBD.

- [x] `P2-02` Phase 5 bloquante avec validation multi-niveaux
  - Attendu: génération RDL + validation XML/XSD/sémantique + blocage si erreur.
  - Preuve: pipeline de validation 3 niveaux et `can_proceed`.
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase5_rdl/rdl_validator_pipeline.py:75` à `:111`

- [x] `P2-03` Export lineage final
  - Attendu: export JSON lineage disponible.
  - Preuve: `LineageQueryService.to_json()` + écriture du fichier lineage.
  - Réf: `Data_viz_pfe-version-py/viz_agent/phase6_lineage/lineage_service.py:15`
  - Réf: `Data_viz_pfe-version-py/viz_agent/main.py:417`

## Validation en cours (itération 1)

- [x] Créer checklist priorisée
- [x] Exécuter vérifications de base (`rg`, `pytest` ciblé)
- [x] Corriger `P0-01` (imports phase 0)
- [x] Corriger `P0-02` (orchestrateur/factory)
- [x] Corriger `P0-03` (enum `source_type`)
- [x] Démarrer `P1-04` (validation continue phase1/2/4)
- [x] Démarrer `P1-05` (lineage continu phase1/2/4)
- [x] Démarrer `P1-06` (self-healing partiel opérationnel)
