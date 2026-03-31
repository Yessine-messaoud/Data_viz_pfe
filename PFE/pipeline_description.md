# 🧠 🔥 Workflow Global du Pipeline Agentique BI

Le système suit un workflow **orienté intention et piloté par un orchestrateur**, où chaque phase est exécutée par un agent spécialisé, avec des mécanismes transverses de **validation continue** et de **traçabilité (lineage)**.

---

# 🧩 🔄 0. Initialisation (Interaction & Cognition Layer)

## 🔹 Étape 0.1 : Input utilisateur

* requête en langage naturel
* artefacts BI (Tableau, RDL, CSV, DB…)

---

## 🔹 Étape 0.2 : Conversation Agent

* comprend la requête
* enrichit le contexte
* gère les ambiguïtés

---

## 🔹 Étape 0.3 : Intent Detection Agent

* transforme la requête en :

  * intention structurée
  * contraintes
  * pipeline cible

---

## 🔹 Étape 0.4 : Orchestrator Agent

* construit dynamiquement le pipeline
* sélectionne les phases à exécuter
* garantit que certaines phases critiques (ex : validation) sont toujours exécutées

---

# ⚙️ 🔥 Phase 0 — Data Extraction Agent

## 🎯 Objectif

Extraire et normaliser toutes les métadonnées des sources de données.

---

## 🔍 Traitements

1. Détection du type de source :

   * Tableau (live / extract)
   * RDL
   * base de données

2. Extraction brute :

   * tables
   * colonnes
   * types
   * schéma

3. Identification des colonnes utilisées :

   * `is_used_in_dashboard`

4. Profiling :

   * `distinct_count`
   * `null_ratio`

5. Détection des relations :

   * foreign keys
   * heuristiques

6. Normalisation :

   * modèle universel (`MetadataModel`)

---

## 📤 Output

```json
{
  "data": { "tables": [...], "columns": [...] },
  "metadata": {
    "source_phase": 0,
    "confidence": 0.95,
    "validation_status": "passed"
  }
}
```

---

## ✅ Validation

* types cohérents
* tables non vides

---

## 🧬 Lineage

```text
Source → Table → Column
```

---

# ⚙️ 🔥 Phase 1 — Parsing Agent

## 🎯 Objectif

Extraire la structure des dashboards BI.

---

## 🔍 Traitements

1. Parsing des fichiers :

   * `.twb`, `.rdl`

2. Extraction :

   * dashboards
   * worksheets
   * visuels
   * filtres
   * mesures

3. Extraction des bindings :

   * colonnes ↔ visuels

4. Layout :

   * position
   * structure

---

## 📤 Output

```json
{
  "data": {
    "dashboards": [...],
    "visuals": [...],
    "bindings": [...]
  },
  "metadata": {...}
}
```

---

## ✅ Validation

* visuels valides
* champs existants

---

## 🧬 Lineage

```text
Column → Visual
```

---

# ⚙️ 🔥 Phase 2 — Semantic Agent (CORE)

## 🎯 Objectif

Construire un **graphe sémantique intelligent**

---

## 🧠 Traitements

### ✔️ Fast Path

* règles métier
* conventions de nommage

### ✔️ LLM Path

* désambiguïsation
* inférence métier

---

## 🔍 Actions

* identification :

  * dimensions
  * mesures
  * KPI
* inférence :

  * relations manquantes
* mapping :

  * données ↔ concepts métier

---

## 📤 Output

```json
{
  "data": {
    "semantic_graph": {...}
  },
  "metadata": {
    "confidence": 0.9
  }
}
```

---

## ✅ Validation

* cohérence des relations
* agrégations valides

---

## 🧬 Lineage

```text
Column → Measure → KPI → Visual
```

---

# ⚙️ 🔥 Phase 3 — Specification Agent

## 🎯 Objectif

Créer une **spécification abstraite indépendante de l’outil**

---

## 🔍 Traitements

* définition :

  * structure du dashboard
  * mapping données
* abstraction :

  * logique métier

---

## 📤 Output

```json
{
  "data": {
    "abstract_spec": {...}
  }
}
```

---

## ✅ Validation

* cohérence structurelle
* complétude

---

## 🧬 Lineage

```text
Semantic → Spec
```

---

# ⚙️ 🔥 Phase 4 — Transformation Agent

## 🎯 Objectif

Adapter les éléments vers le format cible

---

## 🔍 Traitements

* conversion :

  * calculs (DAX, SQL, etc.)
  * types
* adaptation :

  * contraintes outil

---

## 📤 Output

```json
{
  "data": {
    "transformed_objects": {...}
  }
}
```

---

## ✅ Validation

* compatibilité cible
* types corrects

---

## 🧬 Lineage

```text
Spec → Transformed Objects
```

---

# ⚙️ 🔥 Phase 5 — Generation & Validation Agent (OBLIGATOIRE)

## 🎯 Objectif

Générer et valider les artefacts finaux

---

## 🔍 Traitements

* génération :

  * RDL / PBIX / autre
* validation :

  * syntaxique
  * structurelle

---

## 📤 Output

```json
{
  "data": {
    "rdl": "...",
    "validation_report": {...}
  }
}
```

---

## ✅ Validation (critique)

* toujours exécutée
* bloque si erreur

---

## 🧬 Lineage

```text
Transformed → Final Artifact
```

---

# ⚙️ 🔥 Phase 6 — Lineage & Export Agent

## 🎯 Objectif

Exporter et tracer complètement le pipeline

---

## 🔍 Traitements

* génération :

  * lineage global
* export :

  * JSON
  * YAML

---

## 📤 Output

```json
{
  "data": {
    "lineage_graph": {...}
  }
}
```

---

# 🔁 🔥 Validation & Lineage (Transversal)

👉 exécutés après CHAQUE phase

---

## ✅ Validation continue

* vérifie cohérence locale + globale

---

## 🧬 Lineage continu

* construit un graphe complet :

```text
Source → Data → Semantic → Spec → Output
```

---

# 🔄 🔥 Boucle de correction (Self-Healing)

## ❌ Si erreur :

1. Validation détecte
2. Orchestrator identifie phase fautive
3. correction ciblée :

   * heuristique
   * LLM
4. re-exécution partielle

---

# 📊 🔥 Observability Layer

Inclut :

* Validation Agent
* Lineage Agent
* Monitoring
* Correction Logs

---

## 📤 Exemple :

```json
{
  "decision": "LLM used",
  "reason": "ambiguous field",
  "confidence": 0.78
}
```

---

# 🎯 🔥 Conclusion

Le workflow est :

* **modulaire** → agents indépendants
* **adaptatif** → piloté par intention
* **robuste** → validation continue
* **explicable** → lineage complet
* **intelligent** → hybrid LLM + règles

---

