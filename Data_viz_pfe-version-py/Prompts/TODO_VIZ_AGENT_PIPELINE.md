# To Do Detaillee - Viz Agent Pipeline Python v2

## Objectif Global
Construire un pipeline Python complet qui convertit un fichier Tableau TWBX vers un rapport Power BI pagine RDL valide, avec extraction de donnees reelles, validation stricte, et usage LLM limite a l enrichissement semantique et a la traduction d expressions.

## Definition of Done
- Le pipeline s execute de bout en bout sans crash sur le workbook cible.
- Le fichier RDL genere est valide via RDLValidator.
- La fact table detectee est sales_data.
- Les mesures de type FK sont filtrees.
- Les pages sont correctement separees CD_ / PD_ / SO_.
- Les visuels sont correctement mappes chart / tablix / textbox / map.
- Les tests unitaires principaux passent.

## Priorisation
- P0 Blocant: structure, modeles, phase 0, phase 1, validations critiques.
- P1 Coeur: phase 2, phase 3, phase 4, phase 5.
- P2 Finition: robustesse, hardening, integration, documentation.

## Backlog Correctif 2026-04-03 (Pipeline_03)

### P0 - Corrections critiques (a traiter en premier)
- [x] Corriger le nommage des tables techniques (`federated...`) en noms metier exploitables.
  - Cible code: `viz_agent/phase0_extraction/*`, `viz_agent/phase2_semantic/schema_mapper.py`.
  - Critere d acceptation: chaque table finale expose `name` lisible + `source_name`/mapping stable.

- [x] Propager les filtres globaux jusqu au RDL final.
  - Cible code: `phase1_parser/tableau_parser.py` -> `phase3_spec/abstract_spec_builder.py` -> `phase5_rdl/rdl_builder.py`.
  - Critere d acceptation: `<ReportParameters>` present dans le RDL pour les filtres globaux.

- [x] Rendre le mapping visuel strict et supprimer les ambiguites (`chart` generique interdit).
  - Cible code: `phase1_parser/visual_type_mapper.py`, `phase3_spec/visual_decision_engine.py`, `phase3b_validator/abstract_spec_validator.py`.
  - Critere d acceptation: chaque visual a un type metier explicite; fallback controle avec warning.

- [x] Completer la construction des datasets RDL pour inclure structure data + champs utilises.
  - Cible code: `phase4_transform/rdl_dataset_mapper.py`, `phase5_rdl/rdl_builder.py`.
  - Critere d acceptation: tout champ reference par un visual existe dans `DataSet/Fields`.

- [x] Forcer le type de chart explicite dans le XML RDL (pas de default implicite).
  - Cible code: `phase5_rdl/rdl_visual_mapper.py`.
  - Critere d acceptation: chaque `ChartSeries` a `<Type>` (et `<Subtype>` si requis, ex pie).

### P1 - Corrections majeures
- [x] Remplacer les jointures heuristiques `id -> id` par parsing des relations Tableau quand disponibles.
  - Cible code: `phase2_semantic/join_resolver.py`, parsing XML phase 1.
  - Critere d acceptation: les joins du lineage proviennent d abord des relations source.

- [x] Recuperer et propager la semantique de couleur (`color`) jusqu au rendu RDL.
  - Cible code: `phase1_parser/tableau_parser.py`, `phase3_spec/abstract_spec_builder.py`, `phase5_rdl/rdl_visual_mapper.py`.
  - Critere d acceptation: `color` detecte dans l encodage et reflecte dans series/group RDL.

- [x] Stabiliser le graphe semantique (ID deterministes + dedup stricte).
  - Cible code: `phase2_semantic/graph/semantic_graph.py`.
  - Critere d acceptation: no duplicates de noeuds/relations pour un meme input.

- [x] Renforcer la validation semantique bloquante.
  - Cible code: `phase3b_validator/abstract_spec_validator.py`, `phase5_rdl/rdl_semantic_validator.py`.
  - Critere d acceptation: blocage si mesure non numerique ou dimension agregable incorrecte.

### P1/P2 - Structure pipeline et robustesse
- [x] Formaliser un contrat de resultat par phase (`PhaseResult`).
  - Cible code: `viz_agent/main.py` + orchestrateur.
  - Critere d acceptation: chaque phase retourne `ok`, `retry_hint`, `confidence`, `artifacts`.

- [x] Definir et appliquer un rendering contract strict avant ecriture RDL.
  - Cible code: `phase5_rdl/rdl_validator_pipeline.py`, `phase5_rdl/rdl_dataset_validator.py`.
  - Critere d acceptation: blocage si dataset/field mapping incomplet ou incoherent.

- [x] Limiter l auto-fix aux corrections non destructives.
  - Cible code: `phase5_rdl/rdl_auto_fixer.py`.
  - Critere d acceptation: auto-fix autorise seulement renommage/alias/normalisation structurelle.

### P2 - Qualite avancee
- [x] Introduire un score de confidence global cross-phases pour pilotage fast-path/retry.
  - Cible code: `phase2_semantic/*`, `viz_agent/main.py`.
  - Critere d acceptation: score consolide visible dans les artefacts de sortie.

- [x] Activer un cache intelligent par phase (fingerprint + invalidation partielle).
  - Cible code: `phase2_semantic/agentic_semantic_orchestrator.py`, orchestration main.
  - Critere d acceptation: rerun plus rapide sans divergence d artefacts.

- [x] Renforcer observabilite et debug.
  - Cible code: logs pipeline, hooks validation/lineage, exports dashboard.
  - Critere d acceptation: trace lisible phase par phase avec erreurs typees et actions appliquees.

## Verification de cloture de ce backlog
- [x] Tous les points P0 traites et testes.
- [x] Aucun `chart` generique dans les specs de sortie.
- [x] RDL genere valide + explicit chart type pour tous les charts.
- [x] Filtres globaux visibles dans le RDL final (`ReportParameters`).
- [x] Lineage et graph semantique stables (sans duplication).

## Sprint 0 - Setup Projet (P0)
- [x] Creer l arborescence projet complete selon le document.
- [x] Ajouter requirements.txt avec les dependances imposees.
- [x] Initialiser environnement Python 3.11+ et pytest.
- [x] Definir conventions de logs et gestion d erreurs.
- [x] Verifier l installation de lxml, pandas, pydantic v2.

## Sprint 1 - Modeles et Validation de Base (P0)
- [x] Implementer models/abstract_spec.py avec tous les types Pydantic v2.
- [x] Implementer models/validation.py.
- [x] Verifier coherence des types entre phases.
- [x] Ajouter tests de serialisation modeles.

## Sprint 2 - Phase 0 Data Source Layer (P0)
- [x] Implementer phase0_data/hyper_extractor.py.
- [x] Ajouter fallback tableauhyperapi si pantab indisponible.
- [x] Implementer phase0_data/csv_loader.py avec fallback encodage.
- [x] Implementer phase0_data/db_connector.py.
- [x] Implementer phase0_data/data_source_registry.py.
- [x] Verifier all_frames et get_sql_query.
- [x] Ecrire tests test_phase0.py.

## Sprint 3 - Phase 1 Parser Tableau (P0)
- [x] Implementer phase1_parser/tableau_parser.py.
- [x] Lire TWBX ZIP, localiser TWB, parser XML via lxml.
- [x] Extraire worksheets, datasources, dashboards, calc fields, parameters, filters.
- [x] Lier les datasources XML aux donnees reelles du registry.
- [x] Implementer phase1_parser/dashboard_zone_mapper.py sans contamination inter pages.
- [x] Implementer phase1_parser/federated_resolver.py.
- [x] Implementer phase1_parser/visual_type_mapper.py avec fallback propre.
- [x] Ecrire tests test_phase1.py.

## Sprint 4 - Phase 2 Semantique Hybride (P1)
- [x] Implementer phase2_semantic/schema_mapper.py deterministe.
- [x] Implementer phase2_semantic/join_resolver.py deterministe.
- [x] Implementer phase2_semantic/semantic_enricher.py (LLM enrichissement uniquement).
- [x] Implementer phase2_semantic/fact_table_detector.py avec scoring.
- [x] Implementer filter_fk_measures.
- [x] Implementer phase2_semantic/hybrid_semantic_layer.py.
- [x] Ecrire tests test_phase2.py.

## Sprint 5 - Phase 3 AbstractSpec + Validator (P1)
- [x] Implementer phase3_spec/abstract_spec_builder.py.
- [x] Integrer rdl_datasets dans AbstractSpec.
- [x] Implementer phase3b_validator/abstract_spec_validator.py.
- [x] Ajouter regle R001 rdl_datasets vide.
- [x] Ajouter regle M_FACT fact_table invalide.
- [x] Ecrire tests test_phase3.py.

## Sprint 6 - Phase 4 Transformation (P1)
- [x] Implementer phase4_transform/rdl_dataset_mapper.py.
- [x] Mapper types PBI vers types RDL.
- [x] Implementer phase4_transform/calc_field_translator.py.
- [x] Ajouter retry LLM max 3 avec validation intermediaire.
- [x] Integrer validators/expression_validator.py.
- [x] Ajouter correspondances calc fields AdventureWorks.
- [x] Ecrire tests test_phase4.py.

## Sprint 7 - Phase 5 RDL Engine (P1)
- [x] Implementer phase5_rdl/rdl_layout_builder.py en inches 4 decimales.
- [x] Implementer phase5_rdl/rdl_visual_mapper.py.
- [x] Implementer phase5_rdl/rdl_generator.py via lxml.
- [x] Implementer phase5_rdl/rdl_validator.py.
- [x] Verifier DataSources, DataSets, Body, Page obligatoires.
- [x] Verifier references DataSetName des Tablix/Chart.
- [x] Ecrire tests test_phase5_rdl.py.

## Sprint 8 - Phase 6 Lineage + Orchestrateur (P1)
- [x] Implementer phase6_lineage/lineage_service.py.
- [x] Implementer main.py async orchestrant toutes les phases.
- [x] Ajouter saisie secure de la cle Mistral via getpass.
- [x] Ecrire sorties output.rdl et output_lineage.json.
- [x] Bloquer execution si validation non conforme.

## Sprint 9 - Regles Metier AdventureWorks (P0)
- [x] Forcer detection correcte fact table sales_data via scoring.
- [x] Filtrer mesures FK interdites.
- [x] Appliquer mapping pages:
  - [x] Customer Details <- CD_ uniquement
  - [x] Product Details <- PD_ uniquement
  - [x] Sales Overview <- SO_ uniquement
- [x] Appliquer infer_rdl_visual_type sur tous les worksheets.
- [x] Verifier que KPI est mappe en textbox.

## Sprint 10 - Qualite et Stabilisation (P2)
- [x] Ajouter tests d integration pipeline complet sur fichier TWBX demo.
- [x] Ajouter gestion erreurs: fichier absent, XML invalide, dependance Hyper absente.
- [x] Ajouter logs de phase lisibles.
- [x] Ajouter documentation d execution locale.

## Sprint 11 - Semantique Avancee + Graph + Securite (P1/P2)
- [x] Creer ontologie JSON metier (overrideable).
- [x] Implementer OntologyLoader robuste (merge + validation schema).
- [x] Implementer moteur mapping hybride avec scoring et fallback deterministe.
- [x] Integrer driver Neo4j officiel avec configuration par variables d environnement.
- [x] Implementer SemanticGraph CRUD + modelisation noeuds/relations.
- [x] Refactor entrypoint phase 2 via orchestrateur dedie.
- [x] Brancher la phase 2 au pipeline principal.
- [x] Exporter semantic_model JSON incluant artefacts phase 2.
- [x] Verifier compatibilite phase 3 / phase 5.
- [x] Ecrire tests unitaires mapping/ontology/graph + test integration Neo4j local (conditionnel).
- [x] Ajouter exemple usage dataset.
- [x] Mettre a jour README technique.
- [x] Revue securite cle API (suppression hardcode, lecture env).

## Checklist de Verification Finale
- [x] Pipeline execute de la phase 0 a 6 sans erreur bloquante.
- [x] AbstractSpecValidator score acceptable et can_proceed true.
- [x] RDLValidator can_proceed true.
- [x] Pages finales correctes et visuels correctement mappes.
- [x] Aucune cle API hardcodee dans le code.
- [x] Tests unitaires principaux passes.

## Commandes Cibles d Execution
- [x] Installer dependances Python.
- [x] Lancer tests pytest.
- [x] Executer main.py avec input TWBX et output RDL.
- [x] Verifier les artefacts de sortie.

## Etat de Cloture
- Avancement implementation: 100% sur les sprints 0 a 10.
- Validation locale: 27 tests passes, 3 tests integration skips (dependants de MISTRAL_API_KEY / run live).
- Validation live: pipeline execute avec `Input/Ventes par Pays.twbx` et artefacts RDL + lineage generes.
- Reste pour cloture complete: aucun blocant technique identifie.

## Risques et Mitigation
- Risque: Parsing XML Tableau heterogene.
  - Mitigation: fallback robuste + tests sur plusieurs structures TWB.
- Risque: Ambiguite de mapping de champs federated.
  - Mitigation: resolver deterministe + enrichissement LLM borne.
- Risque: RDL invalide malgre generation.
  - Mitigation: validation stricte avant ecriture finale.
- Risque: LLM produit expression invalide.
  - Mitigation: retry max 3 + validator d expression.
