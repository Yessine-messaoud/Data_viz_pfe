Voici un **résumé clair, structuré et priorisé** des améliorations à faire sur ton pipeline 👇

---

# 🔴 1. Problèmes critiques (à corriger en priorité)

### 1. Nommage des tables (`federated...`)

* ❌ Problème : noms techniques non exploitables
* ✅ Fix :

  * récupérer les vrais noms depuis la source (SQL / Tableau XML)
  * ajouter un mapping `physical_name → logical_name`
  * intégrer un **registry de noms métier**

---

### 2. Perte des filtres globaux

* ❌ Problème : extraits en Phase 1 mais absents dans le RDL
* ✅ Fix :

  * propager jusqu’à Phase 5
  * générer `<ReportParameters>` dans le RDL

---

### 3. Mapping visuel incorrect (ex: treemap)

* ❌ Problème : visuels mal convertis
* ✅ Fix :

  * mapping strict `type → RDL`
  * fallback contrôlé (ex: treemap → tablix + warning)
  * interdire `chart` générique

---

### 4. Dataset RDL incomplet

* ❌ Problème : seulement des calculs, pas de structure data
* ✅ Fix :

  * inclure tables + colonnes + lineage
  * garantir : *tout champ utilisé = présent dans dataset*

---

### 5. Type de chart absent dans le RDL

* ❌ Problème : RDL non interprétable correctement
* ✅ Fix :

  * injecter `<ChartType>` explicite
  * aligner avec `visual_type_override`

---

# 🟠 2. Problèmes majeurs détectés

### 6. Jointures incorrectes (JoinResolver)

* ❌ Problème : jointures heuristiques (`id → id`)
* ✅ Fix :

  * parser `<relation>` du XML Tableau
  * fallback heuristique uniquement si absence

---

### 7. Détection des couleurs absente

* ❌ Problème : perte de sémantique visuelle
* ✅ Fix :

  * parser `color` dans les marks Tableau
  * injecter dans `visual_encoding`
  * mapper vers `SeriesGroup` RDL

---

### 8. Graph sémantique instable

* ❌ Problème : duplication / incohérence
* ✅ Fix :

  * IDs déterministes (hash table+column)
  * déduplication stricte

---

### 9. Validation sémantique insuffisante

* ❌ Problème : erreurs passent silencieusement
* ✅ Fix :

  * règles fortes :

    * mesure = numérique
    * dimension ≠ agrégée
  * bloquer si incohérence critique

---

# 🟡 3. Problèmes structurels pipeline

### 10. Pipeline non agentique

* ❌ Problème : pipeline linéaire rigide
* ✅ Fix :

  * introduire un **Agent Loop**
  * chaque phase retourne :

    ```
    PhaseResult(ok, retry_hint, confidence)
    ```
  * possibilité de rollback (ex: Phase 5 → Phase 3)

---

### 11. Absence de “rendering contract”

* ❌ Problème : RDL généré mais non exécutable
* ✅ Fix :

  * définir règles obligatoires :

    * dataset valide
    * champs existants
    * mapping correct
  * sinon → blocage

---

### 12. Auto-fix dangereux

* ❌ Problème : corrections pouvant casser la logique
* ✅ Fix :

  * autoriser seulement :

    * renommage
    * alias
  * interdire :

    * changement de métrique
    * changement de visuel

---

# 🟢 4. Améliorations avancées (qualité & robustesse)

### 13. Système de confidence global

* Score basé sur :

  * parsing
  * mapping
  * validation
* utilisé pour :

  * décider fast path / retry / LLM

---

### 14. Cache intelligent

* ❌ Problème actuel : non utilisé efficacement
* ✅ Fix :

  * cache basé sur fingerprint complet
  * invalidation partielle (par phase)

---

### 15. Observabilité & debug

* Ajouter :

  * logs structurés
  * erreurs typées
  * traces lineage complètes

---

# 🧠 Vision finale cible

Ton pipeline doit évoluer vers :

### 🔁 Pipeline agentique intelligent

* multi-path : fast / cache / LLM
* feedback loop entre phases

### 🧱 Architecture contractuelle

* chaque phase valide + garantit
* aucune donnée ambiguë ne passe

### 🛡️ Robustesse maximale

* validation multi-niveaux
* blocage si incohérence critique


