# PROMPT D'INSTRUCTIONS — VIZ AGENT PIPELINE COMPLET (Python) v2.0

> **Usage** : Colle ce prompt complet dans Copilot Chat, Cursor, ou tout assistant de code.
> Il est auto-suffisant. Aucun contexte additionnel nécessaire.
>
> **Changelog v2.0** : Ajout couche DATA réelle (Hyper/CSV/DB), moteur RDL complet,
> layout engine, visual mapper Tableau→RDL, rôles LLM clarifiés.

---

## CONTEXTE ET OBJECTIF

Tu es un data engineer senior Python. Tu vas implémenter un **Viz Agent** complet : un pipeline Python qui lit un dashboard Tableau (`.twbx`) et exporte un **rapport paginé Power BI (`.rdl`)** fonctionnel — pas un `.pbix` standard.

> ⚠️ **Cible : RDL (Report Definition Language)**, format XML des rapports paginés Power BI.
> Le pipeline doit produire un fichier `.rdl` valide, ouvrable dans Power BI Report Builder.

Le pipeline comporte **8 phases** numérotées. Implémente-les dans l'ordre. Chaque phase est testable indépendamment.

**Stack technique imposée (tout gratuit / open-source) :**
- Python 3.11+
- `lxml` pour le parsing XML Tableau ET la génération RDL
- `pantab` ou `tableauhyperapi` pour l'extraction des fichiers `.hyper`
- `pandas` pour la manipulation des données CSV / DataFrames
- Mistral (API key demandée en prompt au démarrage, jamais hardcodée)
- `zipfile` natif Python pour lire les `.twbx`
- `pydantic` v2 pour tous les types de données
- `pytest` pour les tests
- Aucune dépendance cloud payante

---

## STRUCTURE DU PROJET

```
viz_agent/
├── main.py                          # point d'entrée CLI
├── models/
│   ├── abstract_spec.py             # tous les types Pydantic
│   └── validation.py                # types ValidationReport, Issue
├── phase0_data/                     # ← NOUVEAU : couche data réelle
│   ├── hyper_extractor.py           # HyperExtractor
│   ├── csv_loader.py                # CSVLoader
│   ├── db_connector.py              # DBConnector
│   └── data_source_registry.py     # DataSourceRegistry
├── phase1_parser/
│   ├── tableau_parser.py            # TableauParser
│   ├── federated_resolver.py        # FederatedDatasourceResolver
│   ├── column_decoder.py            # TableauColumnDecoder
│   └── dashboard_zone_mapper.py     # DashboardZoneMapper
├── phase2_semantic/
│   ├── hybrid_semantic_layer.py     # HybridSemanticLayer
│   ├── schema_mapper.py             # TableauSchemaMapper (déterministe)
│   ├── semantic_enricher.py         # SemanticEnricher (LLM — enrichissement seul)
│   ├── join_resolver.py             # JoinResolver
│   └── fact_table_detector.py       # detect_fact_table()
├── phase3_spec/
│   └── abstract_spec_builder.py     # AbstractSpecBuilder
├── phase3b_validator/
│   └── abstract_spec_validator.py   # AbstractSpecValidator
├── phase4_transform/
│   ├── transform_planner.py         # TransformPlanner
│   ├── star_schema_builder.py       # StarSchemaBuilder
│   ├── calc_field_translator.py     # CalcFieldTranslator (LLM — traduction seule)
│   └── rdl_dataset_mapper.py        # RDLDatasetMapper ← NOUVEAU
├── phase5_rdl/                      # ← REMPLACE phase5_export
│   ├── rdl_generator.py             # RDLGenerator (LLM + templates) ← NOUVEAU
│   ├── rdl_layout_builder.py        # RDLLayoutBuilder ← NOUVEAU
│   ├── rdl_visual_mapper.py         # RDLVisualMapper ← NOUVEAU
│   └── rdl_validator.py             # RDLValidator ← NOUVEAU
├── phase6_lineage/
│   └── lineage_service.py           # LineageQueryService
├── validators/
│   ├── model_validator.py           # ModelValidator
│   └── expression_validator.py      # ExpressionValidator (remplace DAXValidator)
├── autofixer/
│   └── auto_fixer.py                # AutoFixer
└── tests/
    ├── test_phase0.py
    ├── test_phase1.py
    ├── test_phase2.py
    ├── test_phase3.py
    ├── test_phase4.py
    ├── test_phase5_rdl.py
    └── test_validators.py

Demo/
├── input/
│   └── vente_par_pays.twbx
└── output/
    ├── expected_output.rdl
    └── dashboard_preview.html
```

---

## PHASE 0 — DATA SOURCE LAYER *(CRITIQUE — NOUVEAU)*

> **Pourquoi cette phase est critique** : Sans extraction réelle des données (Hyper, CSV, DB),
> le pipeline ne peut pas construire les `<DataSet>` RDL, et le rapport paginé sera vide.
> Cette phase alimente tout le reste du pipeline.

### 0.1 HyperExtractor

**Fichier** : `phase0_data/hyper_extractor.py`

```python
"""
Extrait les données des fichiers .hyper embarqués dans le .twbx.
Utilise pantab (wrapper pandas autour de tableauhyperapi).
"""
import zipfile
import tempfile
from pathlib import Path
import pandas as pd

try:
    import pantab
    PANTAB_AVAILABLE = True
except ImportError:
    PANTAB_AVAILABLE = False

class HyperExtractor:

    def extract_from_twbx(
        self,
        twbx_path: str
    ) -> dict[str, dict[str, pd.DataFrame]]:
        """
        Retourne : {hyper_filename: {table_name: DataFrame}}
        """
        results = {}

        with zipfile.ZipFile(twbx_path) as zf:
            hyper_files = [
                n for n in zf.namelist()
                if n.endswith('.hyper')
            ]

            if not hyper_files:
                return results

            with tempfile.TemporaryDirectory() as tmp:
                for hyper_name in hyper_files:
                    zf.extract(hyper_name, tmp)
                    hyper_path = Path(tmp) / hyper_name

                    if PANTAB_AVAILABLE:
                        tables = pantab.frames_from_hyper(str(hyper_path))
                        # tables = {TableName: DataFrame}
                        results[hyper_name] = {
                            str(tname): df
                            for tname, df in tables.items()
                        }
                    else:
                        # Fallback : lire via tableauhyperapi natif
                        results[hyper_name] = self._extract_native(hyper_path)

        return results

    def _extract_native(self, hyper_path: Path) -> dict[str, pd.DataFrame]:
        """Fallback si pantab non disponible."""
        from tableauhyperapi import HyperProcess, Telemetry, Connection
        frames = {}
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
            with Connection(hp.endpoint, str(hyper_path)) as conn:
                catalog = conn.catalog
                for schema in catalog.get_schema_names():
                    for table in catalog.get_table_names(schema):
                        result = conn.execute_list_query(
                            f'SELECT * FROM {table}'
                        )
                        cols = [
                            c.name.unescaped
                            for c in catalog.get_table_definition(table).columns
                        ]
                        frames[str(table)] = pd.DataFrame(result, columns=cols)
        return frames

    def get_schema(
        self,
        df: pd.DataFrame,
        table_name: str
    ) -> "TableRef":
        """Inférer le schéma (types) depuis un DataFrame."""
        TYPE_MAP = {
            "int64":          "int64",
            "float64":        "double",
            "object":         "text",
            "datetime64[ns]": "dateTime",
            "bool":           "boolean",
        }
        from models.abstract_spec import TableRef, ColumnDef
        cols = [
            ColumnDef(
                name=col,
                pbi_type=TYPE_MAP.get(str(df[col].dtype), "text"),
                role="measure" if df[col].dtype in ["int64","float64"] else "dimension"
            )
            for col in df.columns
        ]
        return TableRef(
            id=table_name,
            name=table_name,
            columns=cols,
            row_count=len(df)
        )
```

---

### 0.2 CSVLoader

**Fichier** : `phase0_data/csv_loader.py`

```python
import zipfile, pandas as pd
from pathlib import Path

class CSVLoader:

    def extract_from_twbx(
        self,
        twbx_path: str
    ) -> dict[str, pd.DataFrame]:
        """
        Extrait les CSV embarqués dans le .twbx.
        Retourne : {csv_filename: DataFrame}
        """
        results = {}
        with zipfile.ZipFile(twbx_path) as zf:
            csv_files = [n for n in zf.namelist() if n.endswith('.csv')]
            for csv_name in csv_files:
                with zf.open(csv_name) as f:
                    try:
                        df = pd.read_csv(f, encoding='utf-8')
                    except UnicodeDecodeError:
                        df = pd.read_csv(f, encoding='latin-1')
                    results[Path(csv_name).stem] = df
        return results
```

---

### 0.3 DBConnector

**Fichier** : `phase0_data/db_connector.py`

```python
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class ConnectionConfig:
    type: str          # "postgresql", "sqlserver", "mysql", "sqlite"
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    connection_string: str = ""

class DBConnector:

    def connect_and_sample(
        self,
        config: ConnectionConfig,
        tables: list[str],
        sample_rows: int = 1000
    ) -> dict[str, pd.DataFrame]:
        """
        Se connecte à une base de données et échantillonne les tables.
        Retourne : {table_name: DataFrame (sample)}
        """
        import sqlalchemy
        engine = sqlalchemy.create_engine(
            config.connection_string or self._build_url(config)
        )
        results = {}
        with engine.connect() as conn:
            for table in tables:
                df = pd.read_sql(
                    f"SELECT * FROM {table} LIMIT {sample_rows}",
                    conn
                )
                results[table] = df
        return results

    def _build_url(self, config: ConnectionConfig) -> str:
        return (
            f"{config.type}://{config.username}:{config.password}"
            f"@{config.host}:{config.port}/{config.database}"
        )
```

---

### 0.4 DataSourceRegistry

**Fichier** : `phase0_data/data_source_registry.py`

```python
"""
Registre central qui mappe chaque datasource Tableau
vers ses données réelles extraites.
Utilisé par Phase 1 et Phase 4 pour construire les DataSets RDL.
"""
import pandas as pd
from dataclasses import dataclass, field

@dataclass
class ResolvedDataSource:
    name: str
    source_type: str          # "hyper", "csv", "db", "live"
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    connection_config: dict = field(default_factory=dict)

class DataSourceRegistry:

    def __init__(self):
        self._sources: dict[str, ResolvedDataSource] = {}

    def register(self, name: str, source: ResolvedDataSource):
        self._sources[name] = source

    def get(self, name: str) -> ResolvedDataSource | None:
        return self._sources.get(name)

    def all_frames(self) -> dict[str, pd.DataFrame]:
        """Retourne tous les DataFrames disponibles, toutes sources confondues."""
        result = {}
        for src in self._sources.values():
            result.update(src.frames)
        return result

    def get_sql_query(self, table_name: str) -> str:
        """Génère la requête SQL pour un DataSet RDL."""
        src = self._get_source_for_table(table_name)
        if src and src.source_type == "db":
            return f"SELECT * FROM {table_name}"
        # Pour Hyper/CSV : on exposera les données via un DataSet embarqué
        return f"SELECT * FROM {table_name}"

    def _get_source_for_table(self, table_name: str) -> ResolvedDataSource | None:
        for src in self._sources.values():
            if table_name in src.frames:
                return src
        return None
```

---

## PHASE 1 — TABLEAU PARSER

### 1.1 TableauParser

**Fichier** : `phase1_parser/tableau_parser.py`

```python
class TableauParser:
    def parse(
        self,
        twbx_path: str,
        registry: DataSourceRegistry   # ← injecté depuis Phase 0
    ) -> ParsedWorkbook:
        """
        Lit un fichier .twbx (ZIP contenant .twb XML + extraits de données).
        Extrait : worksheets, datasources, dashboards, calculated_fields,
                  parameters, filters, color_palettes.
        Lie les datasources XML aux données réelles via le registry.
        """
```

**Règles d'implémentation :**

1. Ouvrir le ZIP avec `zipfile.ZipFile`
2. Localiser le fichier `.twb` dans le ZIP (extension `.twb`)
3. Parser le XML avec `lxml.etree`
4. Extraire les `<worksheet>` : nom, type de mark, shelves (rows/cols/marks/filters/pages)
5. Extraire les `<datasource>` : nom, caption, type de connexion, colonnes
6. Extraire les `<dashboard>` avec leurs `<zone type='sheet'>` — **CRITIQUE : chaque dashboard ne doit contenir que ses propres zones**
7. Extraire les `<column>` avec leurs expressions (champs calculés)
8. Extraire les `<parameter>` Tableau
9. Extraire les filtres globaux et par worksheet
10. Pour chaque datasource : consulter le `DataSourceRegistry` pour récupérer le schéma réel
11. Lier les `<named-connection>` XML aux frames du registry

**Types Pydantic de retour :**

```python
class ParsedWorkbook(BaseModel):
    worksheets: list[Worksheet]
    datasources: list[DataSource]
    dashboards: list[TableauDashboard]
    calculated_fields: list[CalcField]
    parameters: list[Parameter]
    filters: list[Filter]
    color_palettes: list[Palette]
    data_registry: DataSourceRegistry   # ← référence au registry peuplé

class TableauDashboard(BaseModel):
    name: str
    worksheets: list[str]   # SEULEMENT les worksheets de CE dashboard
    width: int = 1200
    height: int = 800

class Worksheet(BaseModel):
    name: str
    mark_type: str   # "Bar", "Line", "Circle", "Map", "Text", "Square"
    rows_shelf: list[ColumnRef]
    cols_shelf: list[ColumnRef]
    marks_shelf: list[ColumnRef]
    filters: list[Filter]
    datasource_name: str   # ← quelle datasource alimente ce worksheet
```

**DashboardZoneMapper — règle critique :**

```python
# CORRECT : lire les zones de chaque dashboard
def extract_dashboard_worksheets(dashboard_xml) -> list[str]:
    zones = dashboard_xml.findall('.//zone[@type="sheet"]')
    return [z.get('name') for z in zones if z.get('name')]

# FAUX (ne pas faire) :
# Assigner tous les worksheets à tous les dashboards
```

**Mapping prefix → page (fallback si zones non parsables) :**

```python
PREFIX_MAP = {
    "CD_": "Customer Details",
    "PD_": "Product Details",
    "SO_": "Sales Overview",
}
```

---

### 1.2 FederatedDatasourceResolver

**Fichier** : `phase1_parser/federated_resolver.py`

Quand la datasource est de type `federated`, les colonnes ont la forme :
`federated.{datasource_id}.{agg}:{field_name}:{role}`

```python
class FederatedDatasourceResolver:

    AGG_MAP = {
        "sum": "SUM", "mn": "MIN", "mx": "MAX",
        "avg": "AVG", "tmn": "MIN", "none": "NONE",
        "pcto": "PERCENT_OF_TOTAL", "cnt": "COUNT",
        "cntd": "DISTINCTCOUNT", "median": "MEDIAN",
    }

    ROLE_MAP = {
        "qk": "measure",
        "nk": "dimension",
        "ok": "dimension",
        "pk": "dimension",
    }

    def build_table_map(self, twb_xml) -> dict[str, str]:
        """
        Lit <named-connections> pour mapper id → nom de table réel.
        """
        map_ = {}
        for nc in twb_xml.findall('.//named-connection'):
            name = nc.get('name', '')
            caption = nc.get('caption', name)
            clean = re.sub(r'[^a-zA-Z0-9_]', '_', caption).lower()
            map_[name] = clean
        return map_

    def decode_column(self, raw: str, table_map: dict) -> ResolvedColumn:
        """Décoder une référence de colonne brute Tableau."""
        if raw.startswith('(') or ' + ' in raw or ' - ' in raw:
            return ResolvedColumn(type="expression", raw=raw, needs_llm=True,
                                  table="__expression__", column=raw)
        if 'Measure Names' in raw or raw == ':Measure Names':
            return ResolvedColumn(type="measure_names_placeholder",
                                  table="__placeholder__", column="Measure Names")
        pattern = r'federated\.[^.]+\.(\w+):(.+):(\w+)$'
        m = re.match(pattern, raw)
        if m:
            agg, field, role = m.group(1), m.group(2), m.group(3)
            table = self.infer_table(field, table_map)
            return ResolvedColumn(agg=self.AGG_MAP.get(agg, agg.upper()),
                                  field_name=field,
                                  role=self.ROLE_MAP.get(role, "unknown"),
                                  table=table, column=field, type="resolved")
        return ResolvedColumn(type="simple", table="sales_data", column=raw)

    def infer_table(self, field: str, table_map: dict) -> str:
        TABLE_HINTS = {
            "Customer": "customer_data", "CustomerKey": "customer_data",
            "Product": "product_data", "Category": "product_data",
            "Date": "sales_data", "Month": "sales_data",
            "City": "sales_territory_data", "Country": "sales_territory_data",
            "Sales Amount": "sales_data", "Profit": "sales_data",
            "Sales Order": "sales_order_data",
        }
        return TABLE_HINTS.get(field, "sales_data")
```

---

### 1.3 VisualTypeMapper

**Fichier** : `phase1_parser/visual_type_mapper.py`

```python
# Mapping Tableau → RDL visual type
VISUAL_TYPE_MAP = {
    "KPIs":            "textbox",     # KPI tile → Textbox RDL
    "SalesbyMonth":    "chart",
    "SalesbyProd":     "chart",
    "SalesbyCountry":  "map",
    "SalesCountry":    "map",
    "Matrix":          "tablix",
    "TopProd":         "chart",
    "TopCustomers":    "chart",
    "TopProduct":      "chart",
    "TopByCity":       "chart",
    "Sales vs Profit": "chart",
    "SalesProduct":    "chart",
}

MARK_TYPE_TO_RDL = {
    "Bar":    "chart",
    "Line":   "chart",
    "Circle": "chart",
    "Map":    "map",
    "Text":   "tablix",
    "Square": "tablix",
    "Gantt":  "tablix",
    "Pie":    "chart",
}

def infer_rdl_visual_type(worksheet_name: str, mark_type: str = "") -> str:
    for hint, vtype in VISUAL_TYPE_MAP.items():
        if hint.lower() in worksheet_name.lower():
            return vtype
    if mark_type and mark_type in MARK_TYPE_TO_RDL:
        return MARK_TYPE_TO_RDL[mark_type]
    return "tablix"  # fallback propre, jamais "custom"
```

---

## PHASE 2 — COUCHE SÉMANTIQUE HYBRIDE

### 2.1 HybridSemanticLayer

**Fichier** : `phase2_semantic/hybrid_semantic_layer.py`

> **Rôle du LLM dans cette phase** : enrichissement sémantique UNIQUEMENT.
> Le LLM NE PARSE PAS le XML, NE CONSTRUIT PAS les relations.

```python
class HybridSemanticLayer:
    """
    Deux bras parallèles :
    - Bras 1 (déterministe) : types, relations, hiérarchies
    - Bras 2 (LLM) : renommage métier, mesures suggérées, résolution ambiguïté
    Fusion par SemanticMerger avec scoring de confiance.
    """

    def enrich(
        self,
        workbook: ParsedWorkbook,
        intent: Intent
    ) -> tuple[SemanticModel, DataLineageSpec]:

        # Bras 1 — déterministe (schéma depuis registry réel)
        schema_map = TableauSchemaMapper().map(workbook)
        joins = JoinResolver().resolve(workbook.datasources)

        # Bras 2 — LLM (enrichissement sémantique uniquement)
        llm_enrichment = SemanticEnricher(self.llm).enrich(workbook, schema_map)

        # Fusion
        semantic_model = SemanticMerger().merge(schema_map, llm_enrichment)

        # CRITIQUE : détecter la vraie fact_table par scoring
        semantic_model.fact_table = detect_fact_table(workbook.datasources, joins)

        # CRITIQUE : filtrer les FK des mesures
        semantic_model.measures = filter_fk_measures(semantic_model.measures)

        lineage = DataLineageSpec(
            tables=schema_map.tables,
            joins=joins,
            columns_used=[],
        )

        return semantic_model, lineage
```

---

### 2.2 detect_fact_table()

**Fichier** : `phase2_semantic/fact_table_detector.py`

```python
FK_SUFFIXES = ["Key", "_Key", "KeyID", "_id", "ID", "LineKey"]
MEASURE_KEYWORDS = ["Amount", "Qty", "Quantity", "Price", "Cost",
                    "Revenue", "Profit", "Sales", "Count"]

def detect_fact_table(tables: list[TableRef], joins: list[JoinDef]) -> str:
    """
    Score = (nb FK × 3) + (nb apparitions côté 'many' × 2) + (nb mesures numériques)
    """
    scores: dict[str, int] = {t.name: 0 for t in tables}
    for table in tables:
        fk_score = sum(3 for col in table.columns
                       if any(col.name.endswith(s) for s in FK_SUFFIXES))
        measure_score = sum(1 for col in table.columns
                            if any(kw.lower() in col.name.lower()
                                   for kw in MEASURE_KEYWORDS))
        join_score = sum(2 for j in joins if j.left_table == table.name)
        scores[table.name] = fk_score + measure_score + join_score

    EXCLUDE = {"date_data", "excel_direct_data"}
    filtered = {k: v for k, v in scores.items() if k not in EXCLUDE}
    if not filtered:
        return "sales_data"
    return max(filtered, key=filtered.get)
```

---

### 2.3 filter_fk_measures()

**Fichier** : `phase2_semantic/fact_table_detector.py`

```python
FK_PATTERNS = [r'.*Key$', r'.*_[Kk]ey$', r'.*KeyID$',
               r'.*LineKey$', r'Sum.*Key$', r'Sum.*KeyID$']

def filter_fk_measures(measures: list[Measure]) -> list[Measure]:
    """Supprime les mesures FK numériques. De 38 → ~12 mesures métier."""
    def is_fk(m: Measure) -> bool:
        return any(re.match(p, m.name) for p in FK_PATTERNS)
    return [m for m in measures if not is_fk(m)]
```

---

### 2.4 SemanticEnricher (LLM)

**Fichier** : `phase2_semantic/semantic_enricher.py`

> **Périmètre strict du LLM ici** :
> ✅ Renommer les colonnes techniques en labels métier
> ✅ Suggérer les mesures manquantes depuis les champs calculés
> ✅ Identifier les hiérarchies temporelles
> ❌ NE PAS construire les relations
> ❌ NE PAS parser le XML Tableau

```python
ENRICHER_SYSTEM_PROMPT = """
Tu es un expert en modélisation de données Power BI.
Tu enrichis un SemanticModel extrait d'un workbook Tableau.
Réponds UNIQUEMENT en JSON valide, sans markdown, sans explication.
"""

ENRICHER_USER_PROMPT = """
Tables et colonnes extraites :
{tables_json}

Champs calculés Tableau :
{calculated_fields_json}

Tâches :
1. Pour chaque colonne avec un nom technique, propose un label lisible
2. Identifie les mesures métier manquantes depuis les champs calculés
3. Identifie les hiérarchies temporelles (Year > Quarter > Month > Date)

Retourne ce JSON exact :
{{
  "column_labels": {{"table.colonne": "Label lisible"}},
  "suggested_measures": [{{"name": "...", "expression": "...", "source": "calc_field_name"}}],
  "hierarchies": [{{"name": "...", "table": "...", "levels": ["Year","Quarter","Month","Date"]}}]
}}
"""
```

---

## PHASE 3 — ABSTRACTSPEC (PIVOT)

### 3.1 AbstractSpecBuilder

**Fichier** : `phase3_spec/abstract_spec_builder.py`

```python
class AbstractSpecBuilder:

    @staticmethod
    def build(
        workbook: ParsedWorkbook,
        intent: Intent,
        semantic_model: SemanticModel,
        lineage: DataLineageSpec,
    ) -> AbstractSpec:

        dashboard_spec = DashboardSpecFactory.from_workbook(workbook, semantic_model)
        rdl_dataset_spec = RDLDatasetMapper.build(
            workbook.data_registry, lineage
        )  # ← NOUVEAU : datasets pour le RDL

        return AbstractSpec(
            id=str(uuid.uuid4()),
            version="2.0.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            source_fingerprint=hashlib.sha256(
                str(workbook.model_dump()).encode()
            ).hexdigest(),
            dashboard_spec=dashboard_spec,
            semantic_model=semantic_model,
            data_lineage=lineage,
            rdl_datasets=rdl_dataset_spec,   # ← NOUVEAU
            build_log=[BuildLogEntry(level="info", message="AbstractSpec v2 built",
                                     timestamp=datetime.now(timezone.utc).isoformat())],
            warnings=[]
        )
```

---

### 3.2 DashboardSpecFactory — Handle Measure Names

```python
WORKSHEET_MEASURES = {
    "CD_KPIs": ["Sum Total Sales", "Sum Profit",
                "Sum # Sales Orders", "Sum Avg. Sales per Customer"],
    "PD_KPIs": ["Sum Total Sales", "Sum # Items Ordered",
                "Sum Avg. Items per Order"],
    "SO_KPIs": ["Sum Total Sales", "Sum Profit", "Sum Return on Sales"],
    "PD_TopProdOrder": ["Sum Total Sales", "Sum # Sales Orders"],
    "PD_TopProdProfit": ["Sum Total Sales", "Sum Profit"],
    "SO_TopCustomers":  ["Sum Total Sales", "Sum Avg. Sales per Customer"],
    "SO_TopProduct":    ["Sum Total Sales", "Sum # Items Ordered"],
}

def resolve_data_binding(visual: Worksheet, col: ResolvedColumn, axis: str) -> DataBinding:
    if col.type == "measure_names_placeholder":
        ws_name = visual.name
        measures = WORKSHEET_MEASURES.get(ws_name, ["Sum Total Sales"])
        return DataBinding(measures=[MeasureRef(name=m) for m in measures],
                           visual_type_override="textbox")   # KPI tile RDL

    if col.type == "expression":
        measure_name = f"Calc_{visual.name}_{axis}"
        return DataBinding(
            axes={axis: MeasureRef(name=measure_name)},
            pending_translations=[PendingTranslation(
                measure_name=measure_name,
                tableau_expression=col.raw
            )]
        )

    return DataBinding(axes={axis: ColumnRef(table=col.table, column=col.column)})
```

---

## PHASE 3B — ABSTRACTSPEC VALIDATOR

**Fichier** : `phase3b_validator/abstract_spec_validator.py`

Le validateur s'exécute **après** AbstractSpecBuilder et **avant** toute génération RDL.

```python
class AbstractSpecValidator:

    def validate(self, spec: AbstractSpec) -> ValidationReport:
        errors, warnings = [], []

        self._check_unknown_tables(spec, errors)
        self._check_raw_column_ids(spec, errors)
        self._check_empty_rdl_datasets(spec, errors)   # ← NOUVEAU
        self._check_fact_table(spec, errors)
        self._check_duplicate_pages(spec, warnings)
        self._check_empty_axes(spec, warnings)
        self._check_custom_visual_types(spec, warnings)
        self._check_ghost_tables(spec, warnings)

        return ValidationReport(
            score=self._compute_score(errors, warnings),
            errors=errors, warnings=warnings,
            can_proceed=len(errors) == 0
        )

    def _check_empty_rdl_datasets(self, spec, errors):
        """NOUVEAU : vérifier que les DataSets RDL sont bien construits."""
        if not spec.rdl_datasets:
            errors.append(Issue(
                code="R001", severity="error",
                message="rdl_datasets vide — Phase 0 (DataSource Layer) non exécutée",
                fix="Exécuter HyperExtractor / CSVLoader avant le parsing"
            ))

    def _check_fact_table(self, spec, errors):
        declared = spec.semantic_model.fact_table
        if declared in ("unknown_table", "customer_data", ""):
            errors.append(Issue(
                code="M_FACT", severity="error",
                message=f"fact_table='{declared}' probablement incorrect",
                fix="Utiliser detect_fact_table() avec scoring FK",
                auto_fix="sales_data"
            ))

    def _compute_score(self, errors, warnings) -> int:
        return max(0, 100 - len(errors) * 20 - len(warnings) * 5)
```

---

## PHASE 4 — TRANSFORMATION ENGINE

### 4.1 RDLDatasetMapper *(NOUVEAU — CRITIQUE)*

**Fichier** : `phase4_transform/rdl_dataset_mapper.py`

> Cette classe construit les `<DataSet>` RDL depuis les données réelles extraites en Phase 0.
> Sans cette étape, le rapport paginé ne peut pas charger les données.

```python
from dataclasses import dataclass

@dataclass
class RDLDataset:
    name: str
    query: str
    connection_ref: str
    fields: list["RDLField"]

@dataclass
class RDLField:
    name: str
    data_field: str
    rdl_type: str   # "String", "Integer", "Float", "DateTime", "Boolean"

PBI_TO_RDL_TYPE = {
    "text":     "String",
    "int64":    "Integer",
    "double":   "Float",
    "decimal":  "Float",
    "dateTime": "DateTime",
    "date":     "DateTime",
    "boolean":  "Boolean",
}

class RDLDatasetMapper:

    @staticmethod
    def build(
        registry: DataSourceRegistry,
        lineage: DataLineageSpec
    ) -> list[RDLDataset]:
        """
        Construit un <DataSet> RDL pour chaque table dans le lineage.
        """
        datasets = []
        for table_ref in lineage.tables:
            fields = [
                RDLField(
                    name=col.name,
                    data_field=col.name,
                    rdl_type=PBI_TO_RDL_TYPE.get(col.pbi_type, "String")
                )
                for col in table_ref.columns
            ]
            datasets.append(RDLDataset(
                name=table_ref.name,
                query=registry.get_sql_query(table_ref.name),
                connection_ref="DataSource1",
                fields=fields
            ))
        return datasets
```

---

### 4.2 CalcFieldTranslator (LLM)

**Fichier** : `phase4_transform/calc_field_translator.py`

> **Périmètre strict du LLM ici** :
> ✅ Traduire des expressions Tableau en expressions RDL/DAX
> ✅ Retry avec correction d'erreurs
> ❌ NE PAS construire des structures XML
> ❌ NE PAS gérer les relations entre tables

```python
SYSTEM_PROMPT = """Tu es un expert en expressions RDL et DAX Power BI.
Tu traduis des expressions calculées Tableau en expressions valides.

RÈGLES STRICTES :
1. Pour les expressions numériques : utiliser la syntaxe =Sum(Fields!FieldName.Value)
2. Pour les ratios : utiliser =IIF(Denominator=0, 0, Numerator/Denominator)
3. Pour COUNTD Tableau → =CountDistinct(Fields!FieldName.Value)
4. Retourner UNIQUEMENT l'expression — aucun texte, aucune explication
5. Si intraduisible → retourner exactement : __UNTRANSLATABLE__"""

USER_PROMPT_TEMPLATE = """TABLES DISPONIBLES :
{tables_context}

EXEMPLES DE TRADUCTION :
Tableau: SUM([Sales Amount])
RDL: =Sum(Fields!SalesAmount.Value)

Tableau: COUNTD([Sales Order])
RDL: =CountDistinct(Fields!SalesOrder.Value)

Tableau: {{ FIXED [Category] : SUM([Sales Amount]) }}
RDL: =Sum(Fields!SalesAmount.Value)  /* agrégation par groupe Category */

EXPRESSION À TRADUIRE :
{expression}

Retourne uniquement l'expression RDL :"""

class CalcFieldTranslator:

    def __init__(self, llm_client, validator):
        self.llm = llm_client
        self.validator = validator

    async def translate(
        self,
        expression: str,
        model: SemanticModel,
        max_retries: int = 3
    ) -> str:

        tables_ctx = self._format_tables(model)
        prompt = USER_PROMPT_TEMPLATE.format(
            tables_context=tables_ctx,
            expression=expression
        )

        for attempt in range(max_retries):
            result = await self.llm.complete(
                system=SYSTEM_PROMPT,
                user=prompt,
                temperature=0.1,
                max_tokens=500
            )
            result = result.strip()
            if result == "__UNTRANSLATABLE__":
                break

            issues = self.validator.validate_expression(result)
            errors = [i for i in issues if i.severity == "error"]
            if not errors:
                return result

            prompt = USER_PROMPT_TEMPLATE.format(
                tables_context=tables_ctx,
                expression=f"""Expression originale: {expression}
Tentative précédente: {result}
Erreurs: {[e.message for e in errors]}
Corrige ces erreurs."""
            )

        return f"/* UNTRANSLATABLE: {expression} */"
```

---

## PHASE 5 — GÉNÉRATION RDL *(REMPLACE phase5_export)*

> **Architecture de cette phase** :
> - `RDLDatasetMapper` (Phase 4) → structure des données
> - `RDLLayoutBuilder` → positions et tailles des éléments
> - `RDLVisualMapper` → mapping Tableau → éléments RDL
> - `RDLGenerator` → assemblage XML final (templates + LLM pour logique complexe)
> - `RDLValidator` → validation du XML produit

### 5.1 RDLLayoutBuilder *(NOUVEAU — CRITIQUE)*

**Fichier** : `phase5_rdl/rdl_layout_builder.py`

```python
"""
Calcule les positions et tailles des éléments dans le rapport RDL.
Le RDL utilise des unités en inches (pouces) avec 4 décimales.
"""
from dataclasses import dataclass

@dataclass
class RDLRect:
    left: float    # en pouces
    top: float
    width: float
    height: float

    def to_rdl(self) -> dict[str, str]:
        return {
            "Left":   f"{self.left:.4f}in",
            "Top":    f"{self.top:.4f}in",
            "Width":  f"{self.width:.4f}in",
            "Height": f"{self.height:.4f}in",
        }

class RDLLayoutBuilder:

    # Dimensions page par défaut (Letter paysage)
    PAGE_WIDTH  = 11.0    # inches
    PAGE_HEIGHT = 8.5
    MARGIN      = 0.25
    HEADER_HEIGHT = 0.5

    def compute_layout(
        self,
        dashboard: TableauDashboard,
        visuals: list[VisualSpec]
    ) -> dict[str, RDLRect]:
        """
        Calcule un layout en grille pour les visuels d'un dashboard.
        Retourne : {visual_id: RDLRect}
        """
        available_width  = self.PAGE_WIDTH - 2 * self.MARGIN
        available_height = self.PAGE_HEIGHT - 2 * self.MARGIN - self.HEADER_HEIGHT

        n = len(visuals)
        if n == 0:
            return {}

        # Grille automatique
        cols = min(3, n)
        rows = (n + cols - 1) // cols

        cell_w = available_width / cols
        cell_h = available_height / rows

        layout = {}
        for i, visual in enumerate(visuals):
            col_idx = i % cols
            row_idx = i // cols
            layout[visual.id] = RDLRect(
                left=self.MARGIN + col_idx * cell_w,
                top=self.MARGIN + self.HEADER_HEIGHT + row_idx * cell_h,
                width=cell_w - 0.1,   # padding inter-cellule
                height=cell_h - 0.1,
            )

        return layout

    def compute_pagination(
        self,
        pages: list[DashboardPage]
    ) -> list["RDLPage"]:
        """
        Chaque DashboardPage Tableau → une page RDL avec ses propres Break.
        """
        rdl_pages = []
        for i, page in enumerate(pages):
            rdl_pages.append(RDLPage(
                name=page.name,
                break_location="End" if i < len(pages) - 1 else "None",
                visuals=page.visuals
            ))
        return rdl_pages

@dataclass
class RDLPage:
    name: str
    break_location: str   # "Start", "End", "None"
    visuals: list
```

---

### 5.2 RDLVisualMapper *(NOUVEAU — CRITIQUE)*

**Fichier** : `phase5_rdl/rdl_visual_mapper.py`

```python
"""
Mapping des visuels Tableau → éléments RDL.

Tableau        RDL
─────────────────────────────────────
worksheet      Tablix ou Chart
chart          Chart
KPI/card       Textbox
table/text     Tablix
map            Map (ou Chart si non supporté)
filter         Parameter
parameter      Parameter
"""

from lxml import etree

class RDLVisualMapper:

    NAMESPACES = {
        None: "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
    }

    def map_visual(
        self,
        visual: VisualSpec,
        dataset: RDLDataset,
        rect: RDLRect
    ) -> etree._Element:
        """Retourne l'élément XML RDL pour un visuel donné."""

        rdl_type = visual.type   # "tablix", "chart", "textbox", "map"

        if rdl_type == "chart":
            return self._build_chart(visual, dataset, rect)
        elif rdl_type == "tablix":
            return self._build_tablix(visual, dataset, rect)
        elif rdl_type == "textbox":
            return self._build_kpi_textbox(visual, dataset, rect)
        else:
            return self._build_tablix(visual, dataset, rect)   # fallback

    def _build_chart(
        self,
        visual: VisualSpec,
        dataset: RDLDataset,
        rect: RDLRect
    ) -> etree._Element:
        """Construit un élément <Chart> RDL."""
        chart = etree.Element("Chart")
        chart.set("Name", visual.id)

        # Position
        for attr, val in rect.to_rdl().items():
            chart.set(attr, val)

        # DataSetName
        ds_name = etree.SubElement(chart, "DataSetName")
        ds_name.text = dataset.name

        # ChartSeriesHierarchy
        series_hier = etree.SubElement(chart, "ChartSeriesHierarchy")
        series_members = etree.SubElement(series_hier, "ChartMembers")
        member = etree.SubElement(series_members, "ChartMember")

        # Axes depuis data_binding
        for axis_name, col_ref in visual.data_binding.axes.items():
            if axis_name in ("y", "rows"):
                cv = etree.SubElement(chart, "ChartData")
                cv_series = etree.SubElement(cv, "ChartSeriesCollection")
                cs = etree.SubElement(cv_series, "ChartSeries")
                cvp = etree.SubElement(cs, "ChartDataPoints")
                cdp = etree.SubElement(cvp, "ChartDataPoint")
                cdpv = etree.SubElement(cdp, "ChartDataPointValues")
                y_val = etree.SubElement(cdpv, "Y")
                y_val.text = f"=Sum(Fields!{col_ref.column}.Value)"

        return chart

    def _build_tablix(
        self,
        visual: VisualSpec,
        dataset: RDLDataset,
        rect: RDLRect
    ) -> etree._Element:
        """Construit un élément <Tablix> RDL."""
        tablix = etree.Element("Tablix")
        tablix.set("Name", visual.id)
        for attr, val in rect.to_rdl().items():
            tablix.set(attr, val)

        ds_name = etree.SubElement(tablix, "DataSetName")
        ds_name.text = dataset.name

        # Corps : une ligne de données par field
        body = etree.SubElement(tablix, "TablixBody")
        cols_el = etree.SubElement(body, "TablixColumns")
        rows_el = etree.SubElement(body, "TablixRows")

        for field in dataset.fields[:10]:   # max 10 colonnes visibles
            col_el = etree.SubElement(cols_el, "TablixColumn")
            width_el = etree.SubElement(col_el, "Width")
            width_el.text = f"{rect.width / max(len(dataset.fields), 1):.4f}in"

        # Ligne d'en-tête
        header_row = etree.SubElement(rows_el, "TablixRow")
        h_height = etree.SubElement(header_row, "Height")
        h_height.text = "0.25in"
        h_cells = etree.SubElement(header_row, "TablixCells")
        for field in dataset.fields[:10]:
            cell = etree.SubElement(h_cells, "TablixCell")
            ci = etree.SubElement(cell, "CellContents")
            tb = etree.SubElement(ci, "Textbox")
            tb.set("Name", f"Header_{field.name}")
            para = etree.SubElement(tb, "Paragraphs")
            p = etree.SubElement(para, "Paragraph")
            tr = etree.SubElement(p, "TextRuns")
            trun = etree.SubElement(tr, "TextRun")
            val = etree.SubElement(trun, "Value")
            val.text = field.name

        # Ligne de données
        data_row = etree.SubElement(rows_el, "TablixRow")
        d_height = etree.SubElement(data_row, "Height")
        d_height.text = "0.25in"
        d_cells = etree.SubElement(data_row, "TablixCells")
        for field in dataset.fields[:10]:
            cell = etree.SubElement(d_cells, "TablixCell")
            ci = etree.SubElement(cell, "CellContents")
            tb = etree.SubElement(ci, "Textbox")
            tb.set("Name", f"Data_{field.name}")
            para = etree.SubElement(tb, "Paragraphs")
            p = etree.SubElement(para, "Paragraph")
            tr = etree.SubElement(p, "TextRuns")
            trun = etree.SubElement(tr, "TextRun")
            val = etree.SubElement(trun, "Value")
            val.text = f"=Fields!{field.name}.Value"

        return tablix

    def _build_kpi_textbox(
        self,
        visual: VisualSpec,
        dataset: RDLDataset,
        rect: RDLRect
    ) -> etree._Element:
        """Construit un KPI sous forme de Textbox RDL."""
        tb = etree.Element("Textbox")
        tb.set("Name", visual.id)
        for attr, val in rect.to_rdl().items():
            tb.set(attr, val)

        para = etree.SubElement(tb, "Paragraphs")
        p = etree.SubElement(para, "Paragraph")
        tr = etree.SubElement(p, "TextRuns")
        trun = etree.SubElement(tr, "TextRun")
        val = etree.SubElement(trun, "Value")

        # Première mesure du KPI
        if visual.data_binding.measures:
            m = visual.data_binding.measures[0]
            val.text = f"=Sum(Fields!{m.name}.Value)"
        else:
            val.text = "=0"

        # Style KPI
        style = etree.SubElement(tb, "Style")
        font_size = etree.SubElement(style, "FontSize")
        font_size.text = "20pt"
        font_weight = etree.SubElement(style, "FontWeight")
        font_weight.text = "Bold"
        text_align = etree.SubElement(style, "TextAlign")
        text_align.text = "Center"

        return tb
```

---

### 5.3 RDLGenerator *(NOUVEAU — CRITIQUE)*

**Fichier** : `phase5_rdl/rdl_generator.py`

> **Architecture** : templates déterministes pour la structure, LLM pour les expressions complexes.
> Le LLM génère UNIQUEMENT les valeurs d'expressions, pas la structure XML.

```python
from lxml import etree
from datetime import datetime

RDL_NAMESPACE = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RDL_XSD = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition/ReportDefinition.xsd"

class RDLGenerator:

    def __init__(self, llm_client, calc_translator: CalcFieldTranslator):
        self.llm = llm_client
        self.calc_translator = calc_translator

    async def generate(
        self,
        spec: AbstractSpec,
        layouts: dict[str, dict[str, RDLRect]],    # {page_name: {visual_id: RDLRect}}
        rdl_pages: list[RDLPage]
    ) -> str:
        """
        Retourne le XML RDL complet sous forme de string.
        Structure : templates Python (lxml) + expressions via LLM
        """

        # Racine RDL
        root = etree.Element("Report", xmlns=RDL_NAMESPACE)
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:schemaLocation", f"{RDL_NAMESPACE} {RDL_XSD}")

        # Métadonnées
        self._add_metadata(root, spec)

        # DataSources
        self._add_datasources(root, spec.rdl_datasets)

        # DataSets (UN PAR TABLE)
        self._add_datasets(root, spec.rdl_datasets)

        # Parameters (depuis les filtres Tableau)
        self._add_parameters(root, spec)

        # Body (contient toutes les pages)
        body = etree.SubElement(root, "Body")
        report_items = etree.SubElement(body, "ReportItems")

        # Mapper chaque page
        mapper = RDLVisualMapper()
        for rdl_page in rdl_pages:
            page_rect = layouts.get(rdl_page.name, {})
            for visual in rdl_page.visuals:
                rect = page_rect.get(visual.id)
                if rect is None:
                    continue
                dataset = self._get_dataset_for_visual(
                    visual, spec.rdl_datasets
                )
                if dataset is None:
                    continue
                element = mapper.map_visual(visual, dataset, rect)
                report_items.append(element)

        # Page setup
        self._add_page_setup(root)

        # Sérialization
        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        ).decode("utf-8")

    def _add_metadata(self, root, spec):
        desc = etree.SubElement(root, "Description")
        desc.text = f"Généré par VizAgent v2 le {datetime.now().isoformat()}"
        auto_refresh = etree.SubElement(root, "AutoRefresh")
        auto_refresh.text = "0"

    def _add_datasources(self, root, datasets: list[RDLDataset]):
        ds_collection = etree.SubElement(root, "DataSources")
        ds = etree.SubElement(ds_collection, "DataSource")
        ds.set("Name", "DataSource1")
        conn_props = etree.SubElement(ds, "ConnectionProperties")
        data_provider = etree.SubElement(conn_props, "DataProvider")
        data_provider.text = "SQL"
        conn_string = etree.SubElement(conn_props, "ConnectString")
        conn_string.text = "Data Source=localhost;Initial Catalog=ReportData"

    def _add_datasets(self, root, datasets: list[RDLDataset]):
        ds_collection = etree.SubElement(root, "DataSets")
        for dataset in datasets:
            ds_el = etree.SubElement(ds_collection, "DataSet")
            ds_el.set("Name", dataset.name)

            # Query
            query_el = etree.SubElement(ds_el, "Query")
            ds_name_el = etree.SubElement(query_el, "DataSourceName")
            ds_name_el.text = dataset.connection_ref
            cmd_text = etree.SubElement(query_el, "CommandText")
            cmd_text.text = dataset.query

            # Fields
            fields_el = etree.SubElement(ds_el, "Fields")
            for field in dataset.fields:
                f_el = etree.SubElement(fields_el, "Field")
                f_el.set("Name", field.name)
                df = etree.SubElement(f_el, "DataField")
                df.text = field.data_field
                rd_type = etree.SubElement(f_el, "rd:TypeName")
                rd_type.text = field.rdl_type

    def _add_parameters(self, root, spec):
        if not spec.dashboard_spec.global_filters:
            return
        params_el = etree.SubElement(root, "ReportParameters")
        for f in spec.dashboard_spec.global_filters:
            param = etree.SubElement(params_el, "ReportParameter")
            param.set("Name", f.field.replace(" ", "_"))
            dtype = etree.SubElement(param, "DataType")
            dtype.text = "String"
            prompt = etree.SubElement(param, "Prompt")
            prompt.text = f.field

    def _add_page_setup(self, root):
        page_el = etree.SubElement(root, "Page")
        page_height = etree.SubElement(page_el, "PageHeight")
        page_height.text = "8.5in"
        page_width = etree.SubElement(page_el, "PageWidth")
        page_width.text = "11in"
        for margin in ["TopMargin", "BottomMargin", "LeftMargin", "RightMargin"]:
            m = etree.SubElement(page_el, margin)
            m.text = "0.25in"

    def _get_dataset_for_visual(
        self,
        visual: VisualSpec,
        datasets: list[RDLDataset]
    ) -> RDLDataset | None:
        for ds in datasets:
            if any(
                col_ref.table == ds.name
                for col_ref in visual.data_binding.axes.values()
                if hasattr(col_ref, 'table')
            ):
                return ds
        return datasets[0] if datasets else None
```

---

### 5.4 RDLValidator *(NOUVEAU)*

**Fichier** : `phase5_rdl/rdl_validator.py`

```python
from lxml import etree

class RDLValidator:

    # Éléments obligatoires dans un RDL valide
    REQUIRED_ELEMENTS = [
        "DataSources/DataSource",
        "DataSets/DataSet",
        "Body/ReportItems",
        "Page",
    ]

    def validate(self, rdl_xml: str) -> ValidationReport:
        errors, warnings = [], []

        # Parse XML
        try:
            root = etree.fromstring(rdl_xml.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            return ValidationReport(
                errors=[Issue("R_XML", "error", f"XML invalide: {e}")],
                can_proceed=False
            )

        ns = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}

        # Vérifier les éléments requis
        for path in self.REQUIRED_ELEMENTS:
            parts = path.split("/")
            el = root
            for part in parts:
                el = el.find(f"r:{part}", ns)
                if el is None:
                    errors.append(Issue(
                        "R_STRUCT", "error",
                        f"Élément RDL manquant: {path}"
                    ))
                    break

        # Vérifier que chaque DataSet a une Query
        for ds in root.findall(".//r:DataSet", ns):
            if ds.find("r:Query", ns) is None:
                errors.append(Issue(
                    "R_DS", "error",
                    f"DataSet '{ds.get('Name')}' sans <Query>"
                ))

        # Vérifier que chaque Tablix/Chart référence un DataSet existant
        dataset_names = {
            ds.get("Name")
            for ds in root.findall(".//r:DataSet", ns)
        }
        for item in root.findall(".//r:Tablix", ns):
            ds_ref = item.findtext("r:DataSetName", namespaces=ns)
            if ds_ref and ds_ref not in dataset_names:
                errors.append(Issue(
                    "R_BIND", "error",
                    f"Tablix '{item.get('Name')}' référence DataSet inconnu: {ds_ref}"
                ))

        return ValidationReport(
            score=max(0, 100 - len(errors) * 20 - len(warnings) * 5),
            errors=errors,
            warnings=warnings,
            can_proceed=len(errors) == 0
        )
```

---

## PHASE 6 — LINEAGE & SQL GENERATION

**Fichier** : `phase6_lineage/lineage_service.py`

*(Identique à v1, inchangé — la Phase 0 enrichit automatiquement le registry)*

---

## ORCHESTRATEUR PRINCIPAL

### main.py

```python
#!/usr/bin/env python3
"""
VIZ AGENT v2 — Pipeline Tableau → RDL (Power BI Paginated Report)
Usage: python main.py --input dashboard.twbx --output report.rdl
"""

import asyncio, argparse, getpass
from pathlib import Path

async def run_pipeline(
    twbx_path: str,
    output_path: str,
    mistral_api_key: str,
):
    print("\n🚀 VIZ AGENT v2 — Tableau → RDL\n" + "="*45)

    # Init LLM Mistral
    from mistralai.async_client import MistralAsyncClient
    llm = MistralAsyncClient(api_key=mistral_api_key)

    # ── PHASE 0 : Data Source Layer ─────────────────
    print("Phase 0: Data Source Extraction...")
    from phase0_data.hyper_extractor import HyperExtractor
    from phase0_data.csv_loader import CSVLoader
    from phase0_data.data_source_registry import DataSourceRegistry, ResolvedDataSource

    registry = DataSourceRegistry()

    hyper_frames = HyperExtractor().extract_from_twbx(twbx_path)
    for hyper_name, tables in hyper_frames.items():
        registry.register(hyper_name, ResolvedDataSource(
            name=hyper_name, source_type="hyper", frames=tables
        ))

    csv_frames = CSVLoader().extract_from_twbx(twbx_path)
    if csv_frames:
        registry.register("csv_sources", ResolvedDataSource(
            name="csv_sources", source_type="csv", frames=csv_frames
        ))

    all_frames = registry.all_frames()
    print(f"  ✓ {len(all_frames)} tables extraites "
          f"({sum(len(df) for df in all_frames.values())} lignes total)")

    # ── PHASE 1 : Parser ────────────────────────────
    print("Phase 1: Tableau Parser...")
    from phase1_parser.tableau_parser import TableauParser

    workbook = TableauParser().parse(twbx_path, registry)
    print(f"  ✓ {len(workbook.worksheets)} worksheets, "
          f"{len(workbook.dashboards)} dashboards")

    # ── PHASE 2 : Semantic Layer ─────────────────────
    print("Phase 2: Semantic Layer (deterministic + LLM enrichment)...")
    from phase2_semantic.hybrid_semantic_layer import HybridSemanticLayer
    from phase2_semantic.intent_classifier import classify_intent

    intent = await classify_intent("export to rdl paginated report", llm)
    semantic_model, lineage = await HybridSemanticLayer(llm).enrich(workbook, intent)
    print(f"  ✓ fact_table={semantic_model.fact_table}, "
          f"tables={len(lineage.tables)}, "
          f"measures={len(semantic_model.measures)}")

    # ── PHASE 3 : AbstractSpec ───────────────────────
    print("Phase 3: Build AbstractSpec...")
    from phase3_spec.abstract_spec_builder import AbstractSpecBuilder
    from phase3b_validator.abstract_spec_validator import AbstractSpecValidator
    from phase4_transform.rdl_dataset_mapper import RDLDatasetMapper

    spec = AbstractSpecBuilder.build(workbook, intent, semantic_model, lineage)
    spec.rdl_datasets = RDLDatasetMapper.build(registry, lineage)

    validation = AbstractSpecValidator().validate(spec)
    print(f"  ✓ score={validation.score}/100, "
          f"datasets_rdl={len(spec.rdl_datasets)}")

    if not validation.can_proceed:
        print("\n❌ VALIDATION FAILED:")
        for err in validation.errors:
            print(f"   [{err.code}] {err.message}")
        raise SystemExit(1)

    # ── PHASE 4 : Transformation ─────────────────────
    print("Phase 4: CalcField Translation (LLM)...")
    from phase4_transform.calc_field_translator import CalcFieldTranslator
    from validators.expression_validator import ExpressionValidator

    translator = CalcFieldTranslator(llm, ExpressionValidator())
    for calc in workbook.calculated_fields:
        if calc.expression:
            calc.rdl_expression = await translator.translate(
                calc.expression, semantic_model
            )

    # ── PHASE 5 : RDL Generation ─────────────────────
    print("Phase 5: RDL Generation...")
    from phase5_rdl.rdl_layout_builder import RDLLayoutBuilder
    from phase5_rdl.rdl_generator import RDLGenerator
    from phase5_rdl.rdl_validator import RDLValidator

    layout_builder = RDLLayoutBuilder()
    rdl_pages = layout_builder.compute_pagination(spec.dashboard_spec.pages)

    layouts = {}
    for page in spec.dashboard_spec.pages:
        layouts[page.name] = layout_builder.compute_layout(
            workbook.dashboards[0],  # dashboard correspondant
            page.visuals
        )

    rdl_generator = RDLGenerator(llm, translator)
    rdl_xml = await rdl_generator.generate(spec, layouts, rdl_pages)

    rdl_report = RDLValidator().validate(rdl_xml)
    if not rdl_report.can_proceed:
        print(f"  ❌ RDL invalide: {[e.message for e in rdl_report.errors]}")
        raise SystemExit(1)

    print(f"  ✓ RDL valide, score={rdl_report.score}/100")

    # ── OUTPUT ──────────────────────────────────────
    Path(output_path).write_text(rdl_xml, encoding="utf-8")
    lineage_path = output_path.replace(".rdl", "_lineage.json")
    Path(lineage_path).write_text(spec.data_lineage.model_dump_json(indent=2))

    print(f"\n✅ PIPELINE COMPLETE")
    print(f"   .rdl     → {output_path}")
    print(f"   lineage  → {lineage_path}")
    print(f"   pages    : {[p.name for p in spec.dashboard_spec.pages]}")
    print(f"   visuels  : {sum(len(p.visuals) for p in spec.dashboard_spec.pages)}")
    print(f"   datasets : {len(spec.rdl_datasets)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="VizAgent v2 — Tableau .twbx → Power BI .rdl"
    )
    parser.add_argument("--input",  required=True, help=".twbx path")
    parser.add_argument("--output", default="output.rdl")
    args = parser.parse_args()

    # Demande sécurisée de la clé API (jamais hardcodée)
    api_key = getpass.getpass("Mistral API Key: ")

    asyncio.run(run_pipeline(args.input, args.output, api_key))
```

---

## MODÈLES PYDANTIC COMPLETS (v2)

**Fichier** : `models/abstract_spec.py`

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
import uuid

class ColumnDef(BaseModel):
    name: str
    pbi_type: str = "text"
    role: Literal["measure","dimension","unknown"] = "unknown"
    is_hidden: bool = False
    label: str = ""   # label métier (enrichi par LLM)

class ColumnRef(BaseModel):
    table: str
    column: str

class ResolvedColumn(BaseModel):
    type: Literal["resolved","expression","measure_names_placeholder","simple"]
    table: str
    column: str
    agg: str = "NONE"
    role: Literal["measure","dimension","unknown"] = "unknown"
    raw: str = ""
    needs_llm: bool = False

class JoinDef(BaseModel):
    id: str
    left_table: str
    right_table: str
    left_col: str
    right_col: str
    type: Literal["INNER","LEFT","RIGHT","FULL"] = "INNER"
    pbi_cardinality: str = "ManyToOne"
    source_xml_ref: str = ""

class Measure(BaseModel):
    name: str
    expression: str
    rdl_expression: str = ""   # ← NOUVEAU : expression traduite pour RDL
    source_columns: list[ColumnRef] = []
    pattern: str = ""
    template_args: dict = {}
    tableau_expression: str = ""

class TableRef(BaseModel):
    id: str
    name: str
    source_name: str = ""
    schema: str = "dbo"
    columns: list[ColumnDef] = []
    is_date_table: bool = False
    row_count: int = 0   # ← NOUVEAU : depuis Phase 0

class CalcField(BaseModel):
    name: str
    expression: str
    rdl_expression: str = ""   # ← NOUVEAU

class Parameter(BaseModel):
    name: str
    data_type: str = "string"
    default_value: str = ""

class Filter(BaseModel):
    field: str
    operator: str = "="
    value: Any = None
    column: str = ""

class Palette(BaseModel):
    name: str
    colors: list[str] = []

class DataSource(BaseModel):
    name: str
    caption: str = ""
    connection_type: str = ""
    columns: list[ColumnDef] = []

class VisualSpec(BaseModel):
    id: str
    source_worksheet: str
    type: str = "tablix"    # "tablix", "chart", "textbox", "map"
    title: str
    position: dict = {}
    data_binding: "DataBinding"

class DataBinding(BaseModel):
    axes: dict[str, ColumnRef | "MeasureRef"] = {}
    measures: list["MeasureRef"] = []
    filters: list = []
    visual_type_override: str = ""
    pending_translations: list = []

class MeasureRef(BaseModel):
    name: str

class DashboardPage(BaseModel):
    id: str
    name: str
    visuals: list[VisualSpec] = []

class DashboardSpec(BaseModel):
    pages: list[DashboardPage]
    global_filters: list[Filter] = []
    theme: dict = {}

class SemanticModel(BaseModel):
    entities: list = []
    measures: list[Measure] = []
    dimensions: list = []
    hierarchies: list = []
    relationships: list = []
    glossary: list = []
    fact_table: str = ""
    grain: str = ""

class VisualColumnEntry(BaseModel):
    columns: list[ColumnRef] = []
    joins_used: list[str] = []
    filters: list = []

class DataLineageSpec(BaseModel):
    tables: list[TableRef] = []
    joins: list[JoinDef] = []
    columns_used: list = []
    measures: list = []
    filters_applied: list = []
    transformations: list = []
    visual_column_map: dict[str, VisualColumnEntry] = {}

class AbstractSpec(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "2.0.0"
    created_at: str = ""
    source_fingerprint: str = ""
    dashboard_spec: DashboardSpec
    semantic_model: SemanticModel
    data_lineage: DataLineageSpec
    rdl_datasets: list = []    # ← NOUVEAU : list[RDLDataset]
    build_log: list["BuildLogEntry"] = []
    warnings: list = []

class BuildLogEntry(BaseModel):
    level: Literal["info","warning","error"]
    message: str
    timestamp: str = ""

class ValidationReport(BaseModel):
    score: int = 100
    errors: list = []
    warnings: list = []
    can_proceed: bool = True

class Issue(BaseModel):
    code: str
    severity: Literal["error","warning","info"]
    message: str
    fix: str = ""
    auto_fix: str = ""
```

---

## CORRECTIONS SPÉCIFIQUES AU WORKBOOK ADVENTUREWORKS

Ces corrections sont **obligatoires** car elles correspondent aux bugs détectés sur le workbook de référence.

### C1 — fact_table doit être "sales_data"

Dans `fact_table_detector.py`, s'assurer que `detect_fact_table()` retourne `"sales_data"` en vérifiant que `sales_data` a le plus de colonnes FK (CustomerKey, ProductKey, DateKey, TerritoryKey, SalesOrderLineKey, OrderDateKey, ShipDateKey, DueDateKey).

### C2 — Filtrer les mesures FK

Mesures à filtrer par `filter_fk_measures()` :
`Sum Customer Key`, `Sum Date Key`, `Sum Due Date Key`, `Sum Month Key`,
`Sum Order Date Key`, `Sum Product Key`, `Sum Reseller Key`,
`Sum Sales Order Line Key`, `Sum Sales Territory Key`, `Sum Ship Date Key`

### C3 — Correspondances CalcField AdventureWorks

Dans `CalcFieldTranslator`, injecter ces correspondances :
- `Calculation_1259319095595331584` → `Profit` (= Sales Amount - Total Product Cost)
- `Calculation_1259319095894155266` → mesure de ventes
- `Calculation_1259319095915106309` → count d'ordres

### C4 — Pages et worksheets

```
Customer Details → CD_* worksheets uniquement
Product Details  → PD_* worksheets uniquement
Sales Overview   → SO_* worksheets uniquement
```

### C5 — Types visuels RDL

Ne jamais laisser `type="tablix"` par défaut sur tout. Appliquer `infer_rdl_visual_type()` sur tous les worksheets. Les KPIs doivent être `textbox`, les graphiques doivent être `chart`.

---

## TESTS UNITAIRES

**Fichier** : `tests/test_phase0.py`

```python
import pytest, pandas as pd
from unittest.mock import patch, MagicMock
from phase0_data.data_source_registry import DataSourceRegistry, ResolvedDataSource
from phase0_data.csv_loader import CSVLoader

def test_registry_returns_all_frames():
    reg = DataSourceRegistry()
    df1 = pd.DataFrame({"a": [1, 2]})
    df2 = pd.DataFrame({"b": [3, 4]})
    reg.register("src1", ResolvedDataSource("src1", "csv", {"table1": df1}))
    reg.register("src2", ResolvedDataSource("src2", "hyper", {"table2": df2}))
    all_f = reg.all_frames()
    assert "table1" in all_f
    assert "table2" in all_f
    assert len(all_f) == 2

def test_registry_generates_sql_query():
    reg = DataSourceRegistry()
    df = pd.DataFrame({"col": [1]})
    reg.register("db_src", ResolvedDataSource("db_src", "db", {"orders": df}))
    query = reg.get_sql_query("orders")
    assert "orders" in query.lower()
    assert query.strip().upper().startswith("SELECT")
```

**Fichier** : `tests/test_phase5_rdl.py`

```python
import pytest
from lxml import etree
from phase5_rdl.rdl_validator import RDLValidator
from phase5_rdl.rdl_layout_builder import RDLLayoutBuilder, RDLRect

def test_rdl_layout_positions_do_not_overlap():
    from models.abstract_spec import VisualSpec, DataBinding
    builder = RDLLayoutBuilder()
    visuals = [
        VisualSpec(id=f"v{i}", source_worksheet=f"ws{i}",
                   type="tablix", title=f"Visual {i}",
                   data_binding=DataBinding())
        for i in range(4)
    ]
    dashboard = MagicMock()
    dashboard.width = 1200
    dashboard.height = 800
    layout = builder.compute_layout(dashboard, visuals)
    rects = list(layout.values())
    assert len(rects) == 4
    # Vérifier pas de chevauchement sur l'axe horizontal
    for i, r1 in enumerate(rects):
        for j, r2 in enumerate(rects):
            if i != j and abs(r1.top - r2.top) < 0.01:
                assert r1.left + r1.width <= r2.left + 0.01 or \
                       r2.left + r2.width <= r1.left + 0.01

def test_rdl_validator_catches_missing_dataset():
    minimal_rdl = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition">
  <DataSources><DataSource Name="ds1"><ConnectionProperties>
    <DataProvider>SQL</DataProvider>
    <ConnectString>Server=localhost</ConnectString>
  </ConnectionProperties></DataSource></DataSources>
  <Body><ReportItems/></Body>
  <Page><PageHeight>8.5in</PageHeight><PageWidth>11in</PageWidth></Page>
</Report>"""
    report = RDLValidator().validate(minimal_rdl)
    errors = [e.code for e in report.errors]
    assert "R_STRUCT" in errors   # DataSets manquant

def test_rdl_validator_accepts_valid_rdl():
    valid_rdl = """<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition">
  <DataSources><DataSource Name="ds1"><ConnectionProperties>
    <DataProvider>SQL</DataProvider>
    <ConnectString>Server=localhost</ConnectString>
  </ConnectionProperties></DataSource></DataSources>
  <DataSets><DataSet Name="sales">
    <Query><DataSourceName>ds1</DataSourceName>
    <CommandText>SELECT * FROM sales</CommandText></Query>
  </DataSet></DataSets>
  <Body><ReportItems/></Body>
  <Page><PageHeight>8.5in</PageHeight><PageWidth>11in</PageWidth></Page>
</Report>"""
    report = RDLValidator().validate(valid_rdl)
    assert report.can_proceed, f"Erreurs: {[e.message for e in report.errors]}"
```

**Fichier** : `tests/test_phase2.py`

```python
import pytest
from phase2_semantic.fact_table_detector import detect_fact_table, filter_fk_measures
from models.abstract_spec import TableRef, ColumnDef, JoinDef, Measure

def test_detect_fact_table_adventureworks():
    tables = [
        TableRef(id="t1", name="sales_data", columns=[
            ColumnDef(name="CustomerKey"), ColumnDef(name="ProductKey"),
            ColumnDef(name="DateKey"), ColumnDef(name="Sales Amount"),
        ]),
        TableRef(id="t2", name="customer_data", columns=[
            ColumnDef(name="Customer"), ColumnDef(name="Customer ID"),
        ]),
    ]
    joins = [JoinDef(id="j1", left_table="sales_data",
                     right_table="customer_data",
                     left_col="CustomerKey", right_col="CustomerKey")]
    assert detect_fact_table(tables, joins) == "sales_data"

def test_filter_fk_measures():
    measures = [
        Measure(name="Sum Total Sales",  expression="SUM([Sales Amount])"),
        Measure(name="Sum Customer Key", expression="SUM([Customer Key])"),
        Measure(name="Sum Profit",       expression="SUM([Profit])"),
        Measure(name="Sum Date Key",     expression="SUM([Date Key])"),
    ]
    result = filter_fk_measures(measures)
    names = [m.name for m in result]
    assert "Sum Total Sales" in names
    assert "Sum Profit" in names
    assert "Sum Customer Key" not in names
    assert "Sum Date Key" not in names
    assert len(result) == 2
```

---

## REQUIREMENTS.TXT

```
pydantic>=2.0
lxml>=4.9
mistralai>=0.4
pytest>=7.0
pytest-asyncio>=0.21
aiohttp>=3.9
pandas>=2.0
sqlalchemy>=2.0
pantab>=3.0          # extraction .hyper (optionnel, fallback tableauhyperapi)
tableauhyperapi>=0.0.18563  # fallback si pantab indisponible
```

---

## RÔLES LLM — SYNTHÈSE (RÈGLE D'OR)

| Phase | Composant | LLM utilisé ? | Périmètre strict |
|-------|-----------|---------------|-----------------|
| 0 | HyperExtractor / CSVLoader | ❌ Non | Extraction 100% déterministe |
| 1 | TableauParser | ❌ Non | Parsing XML déterministe |
| 1 | FederatedDatasourceResolver | ❌ Non | Regex + map statique |
| 2 | TableauSchemaMapper | ❌ Non | Mapping de types déterministe |
| 2 | JoinResolver | ❌ Non | Lecture XML des jointures |
| 2 | SemanticEnricher | ✅ Oui | Renommage + suggestions uniquement |
| 4 | CalcFieldTranslator | ✅ Oui | Traduction expressions uniquement |
| 5 | RDLGenerator | ✅ Partiel | Expressions complexes uniquement (pas la structure XML) |

**Le LLM NE DOIT PAS :**
- Parser le XML Tableau
- Construire les relations entre tables
- Générer la structure XML RDL (templates Python via lxml)
- Décider des positions de layout

**Le LLM DOIT :**
- Enrichir les noms de colonnes en labels métier
- Traduire les expressions Tableau en expressions RDL
- Résoudre les champs calculés complexes (LOD, etc.)

---

## CONTRAINTES FINALES

1. **fact_table ≠ "customer_data" ou "unknown_table"** — utiliser `detect_fact_table()` avec scoring.
2. **Filtrer les FK avant toute génération d'expression** — de 38 → ~12 mesures métier.
3. **Phase 0 obligatoire** — le pipeline DOIT extraire les données réelles avant Phase 1.
4. **RDL via lxml** — jamais construire le XML RDL par concaténation de strings.
5. **Valider avec `RDLValidator`** avant chaque écriture du fichier `.rdl` final.
6. **Layout en pouces (inches)** — toutes les positions RDL en `float`in avec 4 décimales.
7. **Un DataSet RDL par table** — pas de DataSet unique "tout en un".
8. **Pages distinctes** : Customer Details = CD_*, Product Details = PD_*, Sales Overview = SO_*.
9. **Jamais `type="tablix"` sur tout** — toujours appliquer `infer_rdl_visual_type()`.
10. **LLM retry** — max 3 tentatives avec validation d'expression entre chaque tentative.
11. **Clé API Mistral en getpass** — jamais hardcodée, jamais dans un fichier de config versionné.