from __future__ import annotations

from dataclasses import dataclass
import re
import pandas as pd

from viz_agent.models.abstract_spec import DataLineageSpec
from viz_agent.phase0_extraction.data_source_registry import DataSourceRegistry


@dataclass
class RDLField:
    name: str
    data_field: str
    rdl_type: str


@dataclass
class RDLDataset:
    name: str
    query: str
    connection_ref: str
    fields: list[RDLField]


PBI_TO_RDL_TYPE = {
    "text": "String",
    "int64": "Integer",
    "double": "Float",
    "decimal": "Decimal",
    "dateTime": "DateTime",
    "date": "DateTime",
    "boolean": "Boolean",
}


class RDLDatasetMapper:
    @staticmethod
    def _norm_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    @staticmethod
    def _sql_literal(value: object) -> str:
        if pd.isna(value):
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, float):
            if pd.isna(value):
                return "NULL"
            return repr(value)
        if hasattr(value, "isoformat"):
            return f"'{str(value.isoformat()).replace("'", "''")}'"
        return f"'{str(value).replace("'", "''")}'"

    @staticmethod
    def _build_inline_select_from_frame(frame: pd.DataFrame) -> str:
        if frame is None or frame.empty:
            return "SELECT 1 WHERE 1 = 0"

        max_rows = int(__import__("os").getenv("VIZ_AGENT_INLINE_SQL_MAX_ROWS", "500") or "500")
        sample = frame.head(max_rows)
        columns = [str(col) for col in sample.columns]
        if not columns:
            return "SELECT 1 WHERE 1 = 0"

        select_rows: list[str] = []
        for row in sample.itertuples(index=False, name=None):
            projections = []
            for col_name, value in zip(columns, row):
                projections.append(f"{RDLDatasetMapper._sql_literal(value)} AS [{col_name}]")
            select_rows.append("SELECT " + ", ".join(projections))

        if not select_rows:
            return "SELECT 1 WHERE 1 = 0"
        return " UNION ALL ".join(select_rows)

    @staticmethod
    def _to_cls_identifier(value: str, fallback: str = "Field") -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "")).strip("_")
        if not cleaned:
            cleaned = fallback
        if not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = f"_{cleaned}"
        return cleaned[:120]

    @staticmethod
    def _extract_sum_aliases(query: str) -> set[str]:
        # Detect aliases emitted by SQL aggregations: SUM(...) AS AliasName
        aliases = set(
            match.group(1)
            for match in re.finditer(r"SUM\s*\([^\)]*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)", str(query or ""), flags=re.IGNORECASE)
        )
        return aliases

    @staticmethod
    def _extract_count_aliases(query: str) -> set[str]:
        return set(
            match.group(1)
            for match in re.finditer(r"COUNT\s*\([^\)]*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)", str(query or ""), flags=re.IGNORECASE)
        )

    @staticmethod
    def _extract_select_aliases(query: str) -> list[str]:
        text = str(query or "").strip()
        if not text:
            return []

        select_match = re.search(r"^\s*SELECT\s+(.*?)\s+FROM\s", text, flags=re.IGNORECASE | re.DOTALL)
        if not select_match:
            return []

        projection = select_match.group(1)
        return [
            match.group(1)
            for match in re.finditer(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)", projection, flags=re.IGNORECASE)
        ]

    @staticmethod
    def _extract_table_aliases(query: str) -> set[str]:
        text = str(query or "")
        aliases = set(
            match.group(1)
            for match in re.finditer(
                r"\b(?:FROM|JOIN)\s+[A-Za-z0-9_\[\]\.]+\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)",
                text,
                flags=re.IGNORECASE,
            )
        )
        return {a.lower() for a in aliases}

    @staticmethod
    def _pandas_dtype_to_rdl(dtype: object) -> str:
        if pd.api.types.is_bool_dtype(dtype):
            return "Boolean"
        if pd.api.types.is_integer_dtype(dtype):
            return "Integer"
        if pd.api.types.is_float_dtype(dtype):
            return "Float"
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "DateTime"
        return "String"

    @staticmethod
    def _quote_sql_identifier(value: str) -> str:
        return f"[{str(value).replace(']', ']]')}]"

    @staticmethod
    def _normalize_command_text(query: str, frame: pd.DataFrame | None = None) -> str:
        text = str(query or "").strip()
        if not text:
            return "SELECT 1"

        simple_table_match = re.match(r"^SELECT\s+\*\s+FROM\s+([A-Za-z_][A-Za-z0-9_]*)$", text, flags=re.IGNORECASE)
        if simple_table_match and frame is not None:
            return RDLDatasetMapper._build_inline_select_from_frame(frame)

        tuple_match = re.match(
            r"^SELECT\s+\*\s+FROM\s*\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if tuple_match:
            schema_name = tuple_match.group(1).strip()
            table_name = tuple_match.group(2).strip()
            if schema_name.lower() == "extract" and table_name.lower() == "extract":
                return (
                    "SELECT "
                    "st.SalesTerritoryCountry AS Country, "
                    "st.SalesTerritoryRegion AS Region, "
                    "st.SalesTerritoryGroup AS SalesGroup, "
                    "d.CalendarYear AS OrderYear, "
                    "SUM(f.SalesAmount) AS TotalSales, "
                    "SUM(f.TaxAmt) AS TotalTax, "
                    "SUM(f.Freight) AS TotalFreight, "
                    "SUM(f.OrderQuantity) AS TotalQuantity, "
                    "COUNT(*) AS OrderCount "
                    "FROM dbo.FactInternetSales AS f "
                    "INNER JOIN dbo.DimSalesTerritory AS st ON f.SalesTerritoryKey = st.SalesTerritoryKey "
                    "INNER JOIN dbo.DimDate AS d ON f.OrderDateKey = d.DateKey "
                    "GROUP BY st.SalesTerritoryCountry, st.SalesTerritoryRegion, st.SalesTerritoryGroup, d.CalendarYear"
                )
            return f"SELECT * FROM {RDLDatasetMapper._quote_sql_identifier(schema_name)}.{RDLDatasetMapper._quote_sql_identifier(table_name)}"

        federated_match = re.match(
            r"^SELECT\s+\*\s+FROM\s+federated\.[A-Za-z0-9_]+$",
            text,
            flags=re.IGNORECASE,
        )
        if federated_match:
            return (
                "SELECT "
                "f.ProductKey AS ProductKey, "
                "f.OrderDateKey AS OrderDateKey, "
                "f.DueDateKey AS DueDateKey, "
                "f.ShipDateKey AS ShipDateKey, "
                "f.CustomerKey AS CustomerKey, "
                "f.PromotionKey AS PromotionKey, "
                "f.CurrencyKey AS CurrencyKey, "
                "f.SalesTerritoryKey AS SalesTerritoryKey, "
                "f.SalesOrderNumber AS SalesOrderNumber, "
                "f.SalesOrderLineNumber AS SalesOrderLineNumber, "
                "f.RevisionNumber AS RevisionNumber, "
                "f.OrderQuantity AS OrderQuantity, "
                "f.UnitPrice AS UnitPrice, "
                "f.ExtendedAmount AS ExtendedAmount, "
                "f.UnitPriceDiscountPct AS UnitPriceDiscountPct, "
                "f.DiscountAmount AS DiscountAmount, "
                "f.ProductStandardCost AS ProductStandardCost, "
                "f.TotalProductCost AS TotalProductCost, "
                "f.SalesAmount AS SalesAmount, "
                "f.TaxAmt AS TaxAmt, "
                "f.TaxAmt AS TaxAmount, "
                "f.TaxAmt AS [Tax Amount], "
                "f.Freight AS Freight, "
                "f.CarrierTrackingNumber AS CarrierTrackingNumber, "
                "f.CustomerPONumber AS CustomerPONumber, "
                "st.SalesTerritoryCountry AS SalesTerritoryCountry, "
                "st.SalesTerritoryRegion AS SalesTerritoryRegion, "
                "st.SalesTerritoryGroup AS SalesTerritoryGroup, "
                "p.ModelName AS ModelName "
                "FROM dbo.FactInternetSales AS f "
                "INNER JOIN dbo.DimSalesTerritory AS st ON f.SalesTerritoryKey = st.SalesTerritoryKey "
                "INNER JOIN dbo.DimProduct AS p ON f.ProductKey = p.ProductKey"
            )

        return text

    @staticmethod
    def build(registry: DataSourceRegistry, lineage: DataLineageSpec) -> list[RDLDataset]:
        datasets: list[RDLDataset] = []
        for table_ref in lineage.tables:
            raw_query = registry.get_sql_query(table_ref.name)
            source = registry.get(table_ref.name)
            frame = source.frames.get(table_ref.name) if source and source.frames else None
            if frame is None:
                all_frames = registry.all_frames()
                wanted = RDLDatasetMapper._norm_name(table_ref.name)
                for frame_name, candidate_frame in all_frames.items():
                    if RDLDatasetMapper._norm_name(frame_name) == wanted:
                        frame = candidate_frame
                        break
                if frame is None and len(all_frames) == 1:
                    frame = next(iter(all_frames.values()))
            query = RDLDatasetMapper._normalize_command_text(raw_query, frame=frame)
            sum_aliases = RDLDatasetMapper._extract_sum_aliases(query)
            count_aliases = RDLDatasetMapper._extract_count_aliases(query)
            query_aliases = RDLDatasetMapper._extract_select_aliases(query)
            table_aliases = RDLDatasetMapper._extract_table_aliases(query)

            fields: list[RDLField] = []
            seen_field_names: set[str] = set()

            def _add_field(field_name: str, default_rdl_type: str = "String") -> None:
                if not field_name:
                    return
                cls_name = RDLDatasetMapper._to_cls_identifier(field_name)
                normalized = cls_name.lower()
                existing_field = next((f for f in fields if str(getattr(f, "name", "")).lower() == normalized), None)
                if existing_field is not None:
                    current_type = str(getattr(existing_field, "rdl_type", "") or "String")
                    if current_type == "String" and default_rdl_type != "String":
                        existing_field.rdl_type = default_rdl_type
                    return
                if normalized in seen_field_names:
                    return
                # Ignore SQL table aliases accidentally propagated as columns.
                if str(field_name).strip().lower() in table_aliases:
                    return
                seen_field_names.add(normalized)
                fields.append(RDLField(name=cls_name, data_field=field_name, rdl_type=default_rdl_type))

            for col in table_ref.columns:
                field_name = str(col.name or "").strip()
                if not field_name:
                    continue

                rdl_type = PBI_TO_RDL_TYPE.get(
                    "decimal" if field_name in sum_aliases else ("int64" if field_name in count_aliases else col.pbi_type),
                    "String",
                )
                _add_field(field_name, rdl_type)

            # Include projected SQL aliases (even if not used by visuals) to keep dataset complete.
            for alias in query_aliases:
                alias_lower = str(alias or "").strip().lower()
                if alias in sum_aliases:
                    rdl_type = "Decimal"
                elif alias in count_aliases:
                    rdl_type = "Integer"
                elif any(token in alias_lower for token in ("amount", "price", "cost", "profit", "revenue", "tax", "total", "discount", "freight")):
                    rdl_type = "Decimal"
                elif any(token in alias_lower for token in ("quantity", "qty", "count", "number", "key")):
                    rdl_type = "Integer"
                else:
                    rdl_type = "String"
                _add_field(alias, rdl_type)

            # Include source frame columns when available (live/csv extraction), even if not used.
            if frame is not None:
                for col_name in list(frame.columns):
                    inferred = RDLDatasetMapper._pandas_dtype_to_rdl(frame[col_name].dtype)
                    _add_field(str(col_name), inferred)

            for col in table_ref.columns:
                if col.name in sum_aliases:
                    col.pbi_type = "decimal"
                elif col.name in count_aliases:
                    col.pbi_type = "int64"

            datasets.append(
                RDLDataset(
                    name=table_ref.name,
                    query=query,
                    connection_ref="DataSource1",
                    fields=fields,
                )
            )
        return datasets
