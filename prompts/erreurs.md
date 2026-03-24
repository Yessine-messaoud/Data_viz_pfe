Tu es un data engineer senior spécialisé Power BI et pipelines de visualisation.

Je travaille sur un agent Viz qui convertit des dashboards Tableau (.twbx) en fichiers Power BI (.pbix). Le pipeline fonctionne (7 étapes passent), mais l'output Power BI est incorrect. Voici les logs exacts :

LOGS PIPELINE :
- Parse Tableau : PASS — 15 worksheets, 3 pages
- Semantic Layer : PASS — fact_table=customer_data, lineage_tables=8, llm_called=true, mode=deterministic-fallback, suggestions=3
- Build AbstractSpec : PASS — id=889a73a0, version=0.1.0
- Transformation engine : PASS — m_queries=20, dax_measures=38
- Export adapter : PASS — target=powerbi, dataset=customer_data_dataset
- Lineage & SQL generation : PASS — columns_used=30, visuals_in_map=15
- LLM Calc Translation : PASS — llm_calls=8, success=1

PROBLÈMES OBSERVÉS DANS LE .PBIX :
1. fact_table = "customer_data" (faux — devrait être "sales_data")
2. 38 mesures DAX dont des foreign keys inutiles (Sum Customer Key, Sum Date Key, Sum Product Key, Sum Product Key, Sum SalesOrderLineKey, Sum SalesTerritoryKey, Sum Ship Date Key)
3. LLM translation : 1 succès / 8 appels — 7 expressions Calculation_* non traduites
4. Champ "Measure Names" copié tel quel depuis Tableau (placeholder virtuel inexistant dans PBI)
5. 3 pages × 15 visuels = 45 visuels (toutes pages identiques — DashboardZoneMapper cassé)
6. Tous les visuels de type "custom" au lieu de card / lineChart / barChart / filledMap / tableEx

CONTEXTE DU MODÈLE DE DONNÉES :
- Workbook source : template_adventurework.twbx
- Tables réelles : customer_data, product_data, reseller_data, sales_order_data, sales_territory_data, sales_data, sales_data (fact), date_data
- La fact table correcte est sales_data (elle contient CustomerKey, ProductKey, DateKey, TerritoryKey, SalesOrderLineKey — toutes les FK)
- Pages réelles attendues :
  * Customer Details → worksheets : CD_KPIs, CD_SalesbyCountry, CD_SalesbyMonth, CD_SalesbyProd, CD_TopByCity&Prod
  * Product Details  → worksheets : PD_KPIs, PD_Matrix, PD_TopProdOrder, PD_TopProdProfit
  * Sales Overview   → worksheets : SO_KPIs, SO_Sales vs Profit, SO_SalesCountry, SO_SalesProduct, SO_TopCustomers, SO_TopProduct
- Mesures métier réelles (depuis glossaire) : Profit, Return on Sales, Total Sales, Avg. Sales Order Value, # Sales Orders, Avg. Sales per Customer, Avg. Items per Order, # Items Ordered

CORRECTIONS À IMPLÉMENTER :

─── FIX 1 — detect_fact_table() ────────────────────────────────
Dans le SemanticLayer (phase 2), remplacer la détection naïve de la fact_table par une détection par score :
- Score FK : nombre de colonnes se terminant par Key, _id, ID
- Score jointures : nombre de fois que la table apparaît côté "many" dans les jointures
- Score mesures : nombre de colonnes numériques agrégables (Amount, Qty, Quantity, Price, Cost)
La table avec le score le plus élevé = fact_table.
Ajouter une règle M_FACT dans le ModelValidator : si fact_table != table inférée, erreur bloquante avec auto_fix.

─── FIX 2 — filter_fk_measures() ───────────────────────────────
Dans le DAXGenerator (phase 4), filtrer les mesures qui sont des clés de jointure avant génération :
- Pattern de filtre : colonnes se terminant par Key, _Key, KeyID, _id, ID, LineKey
- Appliquer ce filtre sur semantic_model.measures AVANT de générer les expressions DAX
- Résultat attendu : de 38 mesures → ~12 mesures métier uniquement

─── FIX 3 — améliorer le prompt LLM pour CalcFieldTranslator ───
Le taux de succès LLM est de 1/8. Améliorer le prompt en injectant :
1. La liste complète des tables et colonnes disponibles dans le modèle
2. Les mesures DAX déjà générées (pour éviter les doublons)
3. Des exemples few-shot de traductions Tableau→DAX pour le workbook AdventureWorks
4. Une validation post-génération avec DAXValidator + retry automatique si erreur
5. Pour les expressions composées (sum(t.col1) + sum(t.col2)), créer une mesure DAX dédiée au lieu de la mettre dans les axes

─── FIX 4 — handle_measure_names() ─────────────────────────────
"Measure Names" est un champ virtuel Tableau multi-mesures. Dans le ColumnDecoder / DashboardSpecFactory :
- Détecter quand column == "Measure Names" ou column == ":Measure Names"
- Remplacer par les mesures concrètes du worksheet en question
- Forcer le type visuel à "card" (KPI tile dans PBI)
- Mapping à implémenter :
  CD_KPIs / PD_KPIs / SO_KPIs → [Sum Total Sales, Sum Profit, Sum # Sales Orders, Sum Avg. Sales per Customer]

─── FIX 5 — DashboardZoneMapper ─────────────────────────────────
Le parser assigne tous les worksheets à toutes les pages. Corriger pour lire les zones XML du .twb :
- Parser les balises  de chaque 
- Si les zones ne sont pas parsables (datasource fédérée), utiliser le préfixe du nom de worksheet :
  CD_* → Customer Details, PD_* → Product Details, SO_* → Sales Overview
- Résultat : 3 pages distinctes avec visuels différents au lieu de 3 pages identiques

─── FIX 6 — VisualTypeMapper ────────────────────────────────────
Inférer le type PBI depuis le nom du worksheet et le mark type XML Tableau :
- KPIs → "card"
- SalesbyMonth, Sales vs Profit → "lineChart"
- SalesbyProd, SalesProduct, TopProd*, TopCustomers, TopProduct, TopByCity → "barChart"
- SalesbyCountry, SalesCountry → "filledMap"
- Matrix → "tableEx"
- Fallback : "tableEx" (pas "custom")

CONTRAINTES :
- Les corrections doivent être dans les bonnes phases (ne pas patcher dans l'Export Adapter ce qui devrait être dans le SemanticLayer)
- Chaque fix doit être testable indépendamment avec un test unitaire
- Les types Python corrects pour PBI : text (pas string), double (pas float), int64 (pas int), dateTime (pas datetime)
- Utiliser Table[Colonne] en DAX, jamais Table.Colonne
- Ajouter les corrections dans le build_log de l'AbstractSpec avec le code du fix appliqué

Pour chaque fix, fournis :
1. Le code corrigé complet (pas juste les parties modifiées)
2. Un test unitaire simple qui vérifie que le fix fonctionne
3. Le message de log à émettre dans build_log quand le fix est appliqué