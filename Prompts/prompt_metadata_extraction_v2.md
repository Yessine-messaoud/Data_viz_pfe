# Prompt — Enterprise Metadata Extraction & Catalog Layer (Phase 0)

---

## Contexte et objectif

Tu es un ingénieur data platform senior. Tu travailles sur un pipeline de conversion
BI (Tableau .twbx → RDL) appelé VizAgent v2.

Tu dois implémenter **Phase 0 : Extraction universelle des métadonnées**.

L'objectif est d'extraire **TOUTES** les métadonnées disponibles dans la source de données,
y compris les tables et colonnes **non utilisées dans le dashboard**, afin de permettre
à l'utilisateur final d'ajouter des visuels en drag & drop après l'export RDL.

---

## Périmètre exact (ne pas dévier)

### Sources supportées dans cette implémentation

| Source | Mode | Mécanisme d'extraction |
|--------|------|------------------------|
| Tableau `.twbx` / `.twb` | **Extract** (fichier `.hyper`) | `tableauhyperapi` |
| Tableau `.twbx` / `.twb` | **Live** (connexion SQL Server) | `SQLAlchemy` + `INFORMATION_SCHEMA` |
| RDL `.rdl` | **Live uniquement** (via `<ConnectString>`) | `SQLAlchemy` + `INFORMATION_SCHEMA` |

> Le mode est détecté automatiquement à partir du XML source.
> Ne pas supporter Power BI dans cette itération.

---

## Détection de mode Tableau (spécification précise)

Lire le fichier `.twb` (XML). Chercher dans `<datasource>` :

```python
# Mode Extract → présence d'un fichier .hyper référencé
if datasource.attrib.get("hasconnection") == "false":
    mode = "extract"
    hyper_path = find_hyper_in_twbx(twbx_path)

# Mode Live → connexion directe
elif connection.attrib.get("class") in ("sqlserver", "mssql", "textscan"):
    mode = "live"
    conn_string = build_sqlalchemy_url(connection.attrib)
```

Clés XML à lire dans `<connection>` :
- `class` → type de driver
- `server`, `dbname`, `schema` → pour construire l'URL SQLAlchemy
- `authentication` → `"sqlserver"` (SQL auth) ou `"sspi"` (Windows auth)

---

## Détection de mode RDL

Lire la balise `<ConnectString>` du RDL :

```python
# Exemple : Data Source=localhost\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022
conn_str = rdl_tree.find(".//ConnectString").text
url = parse_mssql_connect_string(conn_str)  # → SQLAlchemy URL
```

---

## Architecture des modules

```
phase0_extraction/
├── adapters/
│   ├── base_extractor.py          # ABC : interface commune
│   ├── tableau_extractor.py       # Tableau .twbx/.twb
│   └── rdl_extractor.py           # RDL via ConnectString SQL Server
│
├── readers/
│   ├── hyper_reader.py            # tableauhyperapi → RawTableMetadata
│   └── db_reader.py               # SQLAlchemy → RawTableMetadata (MSSQL)
│
├── normalization/
│   └── metadata_normalizer.py     # RawTableMetadata → MetadataModel (Pydantic)
│
├── enrichment/
│   └── column_profiler.py         # distinct_count, null_ratio, rôle dimension/mesure
│
├── relationship_detection/
│   └── relationship_detector.py   # FK SQL + heuristiques suffix "ID"/"Key"
│
├── registry/
│   └── metadata_catalog.py        # MetadataCatalog : get/search/to_json
│
├── export/
│   └── exporter.py                # JSON + YAML
│
├── pipeline.py                    # MetadataExtractor orchestrateur
└── tests/
    ├── test_hyper_reader.py
    ├── test_db_reader.py
    ├── test_normalizer.py
    └── test_relationship_detector.py
```

---

## Modèle de données universel (Pydantic strict)

```python
from pydantic import BaseModel, Field
from typing import Literal

class Column(BaseModel):
    name: str
    type: str                          # type SQL natif : "VARCHAR", "DECIMAL", etc.
    table: str
    nullable: bool | None = None
    is_used_in_dashboard: bool = False # True si référencé dans un visuel source
    role: Literal["dimension", "measure", "unknown"] = "unknown"
    distinct_count: int | None = None
    null_ratio: float | None = None    # 0.0 → 1.0

class Table(BaseModel):
    name: str
    schema_name: str | None = None
    columns: list[Column]
    row_count: int | None = None
    is_used_in_dashboard: bool = False # True si au moins 1 colonne utilisée

class Relationship(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    type: Literal["foreign_key", "inferred_suffix", "inferred_name"]

class MetadataModel(BaseModel):
    source_type: Literal["hyper", "live_sql", "rdl_live"]
    source_path: str
    tables: list[Table]
    relationships: list[Relationship]
    extraction_warnings: list[str] = Field(default_factory=list)
    metadata_version: str = "v1"
```

> **Le champ `is_used_in_dashboard`** est la clé qui permet au frontend
> de distinguer les colonnes actives des colonnes disponibles pour le drag & drop.

---

## Spécification par module

### `adapters/base_extractor.py`

```python
from abc import ABC, abstractmethod

class BaseExtractor(ABC):

    @abstractmethod
    def detect_mode(self, source_path: str) -> str:
        """Retourne : 'extract' | 'live_sql' | 'rdl_live'"""

    @abstractmethod
    def extract_raw(self, source_path: str) -> dict:
        """
        Retourne un dict contenant :
        - tables: list[dict]  (nom, schema, colonnes brutes)
        - used_columns: set[tuple[str,str]]  (table, colonne) utilisées dans les visuels
        - connection_info: dict | None
        - hyper_path: str | None
        """

    @abstractmethod
    def extract_used_columns(self, source_path: str) -> set[tuple[str, str]]:
        """
        Parse les visuels du dashboard source pour identifier
        les (table, colonne) effectivement référencées.
        Utilisé pour peupler is_used_in_dashboard.
        """
```

---

### `adapters/tableau_extractor.py`

Doit implémenter `BaseExtractor`.

Logique de `detect_mode` :
1. Dézipper le `.twbx` si nécessaire
2. Lire le `.twb` XML
3. Chercher `<datasource hasconnection="false">` → mode extract
4. Sinon lire `<connection class="...">` → mode live

Logique de `extract_used_columns` :
- Parser les `<column>` dans les `<worksheet>` → `<datasource-dependencies>`
- Retourner un set de `(datasource_name, column_name)`

---

### `adapters/rdl_extractor.py`

Doit implémenter `BaseExtractor`.

- `detect_mode` → toujours `"rdl_live"`
- Lire `<ConnectString>` → construire URL SQLAlchemy MSSQL
- `extract_used_columns` → parser les `<Field>` de chaque `<DataSet>`
  et les `=Fields!X.Value` dans les expressions des visuels

---

### `readers/hyper_reader.py`

```python
from tableauhyperapi import HyperProcess, Telemetry, Connection, TableName

def list_all_tables(hyper_path: str) -> list[dict]:
    """Liste toutes les tables dans tous les schémas du fichier .hyper."""

def get_table_schema(hyper_path: str, schema: str, table: str) -> list[dict]:
    """Retourne les colonnes avec nom, type SQL, nullable."""

def get_row_count(hyper_path: str, schema: str, table: str) -> int:
    """COUNT(*) — utiliser uniquement si row_count demandé."""
```

Contrainte : ne **pas** charger les données, uniquement le schéma.
Utiliser `connection.catalog.get_table_definition(TableName(...))`.

---

### `readers/db_reader.py`

```python
def extract_all_tables(engine) -> list[dict]:
    """
    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    """

def extract_columns(engine, schema: str, table: str) -> list[dict]:
    """
    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table
    """

def extract_foreign_keys(engine) -> list[dict]:
    """
    Requête sur INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    + KEY_COLUMN_USAGE pour obtenir source/target table+colonne.
    """

def safe_connect(connection_url: str):
    """
    Retourne (engine, None) si succès.
    Retourne (None, error_message) si échec — ne jamais lever d'exception.
    """
```

---

### `normalization/metadata_normalizer.py`

```python
def normalize(raw: dict, used_columns: set[tuple[str,str]]) -> MetadataModel:
    """
    Transforme le dict brut en MetadataModel Pydantic.
    Peuple is_used_in_dashboard en croisant avec used_columns.
    Infère role (dimension/measure) via type SQL :
      - DECIMAL, FLOAT, INT, BIGINT → measure
      - VARCHAR, NVARCHAR, DATE, BIT → dimension
    """
```

---

### `enrichment/column_profiler.py`

Profiling **optionnel** basé sur un échantillon (LIMIT 1000 lignes max) :

```python
def profile_column(engine, schema: str, table: str, column: str) -> dict:
    """
    Retourne : { distinct_count: int, null_ratio: float }
    En mode hyper : utiliser tableauhyperapi avec LIMIT.
    En mode live : SQL avec COUNT(DISTINCT) et COUNT(CASE WHEN IS NULL).
    Ne jamais charger toutes les données.
    """
```

---

### `relationship_detection/relationship_detector.py`

Deux stratégies, appliquées dans l'ordre :

```python
def detect_from_fk(engine) -> list[Relationship]:
    """Lire les FK depuis INFORMATION_SCHEMA (mode live seulement)."""

def detect_from_heuristics(tables: list[Table]) -> list[Relationship]:
    """
    Règles heuristiques :
    1. Si colonne.name.endswith("ID") ou endswith("Key") :
       chercher une table dont le nom correspond au préfixe.
       Ex: CustomerID → table Customer, colonne CustomerID ou ID
    2. Si colonne.name == autre_table.name + "ID" : match direct.
    type = "inferred_suffix"
    """
```

---

### `registry/metadata_catalog.py`

```python
class MetadataCatalog:

    def __init__(self, model: MetadataModel): ...

    def get_tables(self, used_only: bool = False) -> list[Table]:
        """Si used_only=True, ne retourner que les tables is_used_in_dashboard=True."""

    def get_columns(self, table_name: str, used_only: bool = False) -> list[Column]: ...

    def search(self, keyword: str) -> list[Column]:
        """Recherche insensible à la casse dans name et table."""

    def get_available_for_dragdrop(self) -> list[Column]:
        """Retourne les colonnes avec is_used_in_dashboard=False — le catalogue drag & drop."""

    def to_json(self, path: str) -> None: ...

    def to_yaml(self, path: str) -> None: ...
```

---

### `pipeline.py` — Orchestrateur

```python
class MetadataExtractor:

    def extract(self, source_path: str, enable_profiling: bool = False) -> MetadataModel:
        """
        1. Détecter le format (extension : .twbx/.twb → Tableau, .rdl → RDL)
        2. Instancier l'adapter approprié
        3. Détecter le mode (extract vs live)
        4. Extraire les colonnes utilisées dans les visuels (used_columns)
        5. Extraire les métadonnées brutes (toutes les tables/colonnes)
        6. Normaliser → MetadataModel
        7. Profiling optionnel (si enable_profiling=True)
        8. Détecter les relations (FK + heuristiques)
        9. Retourner MetadataModel
        """

    def _detect_format(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext in (".twbx", ".twb"): return "tableau"
        if ext == ".rdl": return "rdl"
        raise ValueError(f"Format non supporté : {ext}")
```

**Gestion des erreurs :**
- Si la connexion DB échoue → ajouter un warning dans `MetadataModel.extraction_warnings`,
  continuer avec les métadonnées partielles disponibles (ex: schéma Hyper uniquement)
- Ne jamais lever d'exception non catchée en dehors du pipeline

---

## Caching

Implémenter un cache fichier simple dans `pipeline.py` :

```python
import hashlib, json
from pathlib import Path

CACHE_DIR = Path(".vizagent_cache")

def _cache_key(source_path: str) -> str:
    mtime = Path(source_path).stat().st_mtime
    return hashlib.md5(f"{source_path}:{mtime}".encode()).hexdigest()

def _load_cache(key: str) -> MetadataModel | None:
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return MetadataModel.model_validate_json(cache_file.read_text())
    return None

def _save_cache(key: str, model: MetadataModel) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(model.model_dump_json())
```

Invalidation : basée sur `mtime` du fichier source → si le fichier change, le cache est ignoré.

---

## Tests

### `test_hyper_reader.py`

```python
def test_list_all_tables(sample_hyper_path):
    tables = list_all_tables(sample_hyper_path)
    assert len(tables) > 0
    assert all("name" in t and "columns" in t for t in tables)

def test_schema_extraction(sample_hyper_path):
    cols = get_table_schema(sample_hyper_path, "Extract", "Extract")
    assert any(c["name"] == "TotalSales" for c in cols)
    assert any(c["type"] in ("DOUBLE PRECISION", "DECIMAL") for c in cols)

def test_no_data_loaded(sample_hyper_path):
    # Vérifier que row_count n'est PAS appelé par défaut
    with patch("hyper_reader.get_row_count") as mock:
        list_all_tables(sample_hyper_path)
        mock.assert_not_called()
```

### `test_db_reader.py`

```python
def test_safe_connect_unreachable():
    engine, err = safe_connect("mssql+pyodbc://bad_host/bad_db?driver=...")
    assert engine is None
    assert err is not None

def test_extract_columns(live_engine):
    cols = extract_columns(live_engine, "dbo", "FactInternetSales")
    assert any(c["name"] == "SalesAmount" for c in cols)
```

### `test_normalizer.py`

```python
def test_is_used_in_dashboard_flag():
    used = {("Extract", "TotalSales")}
    model = normalize(raw_dict_fixture, used)
    sales_col = next(c for t in model.tables for c in t.columns if c.name == "TotalSales")
    assert sales_col.is_used_in_dashboard is True

def test_unused_columns_present():
    model = normalize(raw_dict_fixture, used_columns=set())
    all_cols = [c for t in model.tables for c in t.columns]
    # Toutes les colonnes doivent être présentes même si non utilisées
    assert len(all_cols) == EXPECTED_TOTAL_COLUMNS
```

### `test_relationship_detector.py`

```python
def test_inferred_customer_id():
    tables = [
        Table(name="Orders", columns=[Column(name="CustomerID", type="INT", table="Orders")]),
        Table(name="Customer", columns=[Column(name="CustomerID", type="INT", table="Customer")]),
    ]
    rels = detect_from_heuristics(tables)
    assert any(r.source_column == "CustomerID" and r.target_table == "Customer" for r in rels)

def test_no_false_positive_on_short_names():
    # "ID" seul ne doit pas matcher toutes les tables
    tables = [Table(name="Orders", columns=[Column(name="ID", type="INT", table="Orders")])]
    rels = detect_from_heuristics(tables)
    assert len(rels) == 0
```

---

## Exemple de sortie JSON

```json
{
  "source_type": "hyper",
  "source_path": "/data/sales.twbx",
  "metadata_version": "v1",
  "extraction_warnings": [],
  "tables": [
    {
      "name": "Extract",
      "schema_name": "Extract",
      "row_count": 41,
      "is_used_in_dashboard": true,
      "columns": [
        {
          "name": "Country",
          "type": "VARCHAR",
          "table": "Extract",
          "nullable": false,
          "is_used_in_dashboard": true,
          "role": "dimension",
          "distinct_count": 6,
          "null_ratio": 0.0
        },
        {
          "name": "TotalSales",
          "type": "DECIMAL",
          "table": "Extract",
          "nullable": false,
          "is_used_in_dashboard": true,
          "role": "measure",
          "distinct_count": 40,
          "null_ratio": 0.0
        },
        {
          "name": "DiscountAmount",
          "type": "DECIMAL",
          "table": "Extract",
          "nullable": true,
          "is_used_in_dashboard": false,
          "role": "measure",
          "distinct_count": null,
          "null_ratio": null
        }
      ]
    }
  ],
  "relationships": [
    {
      "source_table": "Orders",
      "source_column": "CustomerID",
      "target_table": "Customer",
      "target_column": "CustomerID",
      "type": "inferred_suffix"
    }
  ]
}
```

---

## Livrables attendus

Générer dans l'ordre :

1. `adapters/base_extractor.py` — ABC avec docstrings
2. `adapters/tableau_extractor.py` — implémentation complète Extract + Live
3. `adapters/rdl_extractor.py` — extraction via ConnectString
4. `readers/hyper_reader.py` — avec `tableauhyperapi`
5. `readers/db_reader.py` — avec SQLAlchemy + `safe_connect`
6. `normalization/metadata_normalizer.py` — avec gestion `is_used_in_dashboard`
7. `enrichment/column_profiler.py` — sampling 1000 lignes max
8. `relationship_detection/relationship_detector.py`
9. `registry/metadata_catalog.py` — avec `get_available_for_dragdrop()`
10. `pipeline.py` — orchestrateur avec cache
11. `tests/` — 4 fichiers de tests

Pour chaque fichier : code complet, typé, documenté, prêt à l'emploi.
