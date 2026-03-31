# Phase 2 — Hybrid Semantic Layer

## Objectif
Construire un modèle sémantique enrichi à partir du workbook Tableau, en combinant logique locale et enrichissement LLM (Mistral). Générer le modèle sémantique et le lineage des données.

## Fonctionnalités principales
- **Mapping du schéma** Tableau → modèle universel
- **Résolution des jointures** entre sources
- **Profiling des colonnes** (statistiques, types)
- **Détection de la fact table** et des mesures clés
- **Enrichissement sémantique** (LLM, ontologies, heuristiques)
- **Fusion sémantique** de plusieurs sources
- **Génération du lineage** (tables, colonnes, relations)
- **Export** du modèle sémantique et du lineage

## Structure des modules
- `hybrid_semantic_layer.py` : Orchestrateur principal
- `fact_table_detector.py` : Détection de la table de faits
- `join_resolver.py` : Résolution des jointures
- `profiling/` : Profiling des colonnes
- `schema_mapper.py` : Mapping du schéma Tableau
- `semantic_enricher.py` : Enrichissement sémantique
- `semantic_merger.py` : Fusion de modèles
- `ontology/` : Gestion des ontologies
- `mapping/` : Moteur de mapping sémantique

## Usage rapide
```python
from viz_agent.phase2_semantic.hybrid_semantic_layer import HybridSemanticLayer
layer = HybridSemanticLayer(llm_client)
semantic_model, lineage = layer.enrich(parsed_workbook)
```

## Notes
- Utilise le LLM Mistral pour l’enrichissement sémantique.
- Profiling non bloquant si les frames ne sont pas disponibles.