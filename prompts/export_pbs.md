🚨 🧠 TODO — Problèmes & Solutions (export non fonctionnel)
🔴 1. DATA SOURCE NON UTILISÉE (HYPER ignoré)

Problème
→ Le système utilise uniquement les données des visualisations

Impact
❌ Dataset incomplet
❌ Relations perdues
❌ Export Power BI incorrect

Solution

Parser .hyper ou datasource XML
Extraire TOUTES les tables
Construire semantic_model.entities complet

To Do

 ✅ Implémenter HyperExtractor
 ✅ Extraire tables + colonnes + types
 ✅ Ajouter preview (5 lignes)

Priorité : 🔥🔥🔥 CRITIQUE

🔴 2. DATA BINDING INCOMPLET

Problème

x = -
y = -

Impact
❌ Visuels inutilisables
❌ Perte de logique métier

Solution

Compléter DataBinding.axes
Mapper correctement :
rows → y
columns → x

To Do

 ✅ Corriger mapping rows/cols → axes x/y (fallback robuste)
 ✅ Ajouter fallback axes via colonnes datasource si shelves vides
 ✅ Ajouter validation stricte (fail si visuel sans binding)

Priorité : 🔥🔥🔥

🔴 3. CALCULS NON TRADUITS (Tableau → DAX)

Problème

Calculation_12345

Impact
❌ Mesures inutilisables
❌ Pas de logique dans Power BI

Solution

Implémenter CalcFieldTranslator
Traduire vers DAX

To Do

 ✅ Templates (SUM, AVG, COUNTD→DISTINCTCOUNT)
 ✅ Branche LLM pour calculs complexes
 ✅ Stockage dans dax_measures (semantic -> transform)

Priorité : 🔥🔥🔥

🔴 4. ABSENCE DE M QUERY (DATASET NON CHARGÉ)

Problème
→ Pas de requêtes Power Query

Impact
❌ Power BI ne peut pas charger les données

Solution

Implémenter MQueryBuilder

To Do

 ✅ Générer 1 requête M par table
 ✅ Injecter dans ExportManifest
 ✅ Alimenter les requêtes via full_table_profiles + sample_data

Priorité : 🔥🔥🔥

🔴 5. RELATIONS NON DÉFINIES

Problème
→ Pas de joins exploitables

Impact
❌ Modèle Power BI cassé

Solution

Implémenter JoinResolver

To Do

 ⚠️ Parser <relation> XML complet (reste à enrichir selon toutes variantes Tableau)
 ✅ Créer JoinDef (inférence par colonnes partagées)
 ✅ Mapper vers relationships Power BI

Priorité : 🔥🔥🔥

🔴 6. EXPORT PBIX NON RÉEL

Problème
→ Export = HTML uniquement

Impact
❌ Pas de fichier Power BI utilisable

Solution

Implémenter vrai export via adapter

To Do

 ✅ Générer structure modèle/layout JSON
 ✅ Assembler un artefact .pbix valide pour pipeline interne
 ⚠️ Export PBIX 100% natif Microsoft (binaire officiel) reste hors scope actuel

Priorité : 🔥🔥🔥

🟠 7. SEMANTIC LAYER INCOMPLÈTE

Problème
→ Mapping partiel

Impact
⚠️ Résultats incohérents

Solution

Compléter pipeline hybride

To Do

 ✅ SchemaMapper OK
 ✅ SemanticEnricher (LLM mock/branch)
 ✅ SemanticMerger avec score

Priorité : 🔥🔥

🟠 8. HTML DEBUG INSUFFISANT

Problème
→ Difficulté de debug

Impact
⚠️ difficile de comprendre erreurs

Solution

Enrichir HTML

To Do

 ✅ Ajouter tables détectées
 ✅ Ajouter preview (5 lignes)
 ✅ Ajouter relations
 ✅ Ajouter DAX measures

Priorité : 🔥🔥

🟡 9. VALIDATION MANQUANTE

Problème
→ erreurs passent silencieusement

Impact
⚠️ pipeline non fiable

Solution

Ajouter validation layer

To Do

 ✅ Fail si table absente
 ✅ Warn si colonne inconnue
 ✅ Vérifier cohérence visuels

Priorité : 🔥🔥

🟡 10. TRAÇABILITÉ PARTIELLE

Problème
→ lineage incomplet

Impact
⚠️ difficile à expliquer / debug

Solution

enrichir DataLineageSpec

To Do

 ✅ Ajouter full_tables
 ✅ Ajouter sampled_rows
 ✅ Ajouter sql_equivalents

Priorité : 🔥

🏆 🎯 PLAN D’ACTION RECOMMANDÉ

👉 Ordre optimal :

1. HyperExtractor (DATA)
2. DataBinding fix
3. JoinResolver
4. CalcFieldTranslator (DAX)
5. MQueryBuilder
6. Export PBIX
7. HTML debug