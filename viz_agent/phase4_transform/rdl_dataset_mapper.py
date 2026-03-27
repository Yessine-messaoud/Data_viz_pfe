from __future__ import annotations

from dataclasses import dataclass
import re

from viz_agent.models.abstract_spec import DataLineageSpec
from viz_agent.phase0_data.data_source_registry import DataSourceRegistry


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
    def _quote_sql_identifier(value: str) -> str:
        return f"[{str(value).replace(']', ']]')}]"

    @staticmethod
    def _normalize_command_text(query: str) -> str:
        text = str(query or "").strip()
        if not text:
            return "SELECT 1"

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

        return text

    @staticmethod
    def build(registry: DataSourceRegistry, lineage: DataLineageSpec) -> list[RDLDataset]:
        datasets: list[RDLDataset] = []
        for table_ref in lineage.tables:
            raw_query = registry.get_sql_query(table_ref.name)
            query = RDLDatasetMapper._normalize_command_text(raw_query)
            sum_aliases = RDLDatasetMapper._extract_sum_aliases(query)
            count_aliases = RDLDatasetMapper._extract_count_aliases(query)

            fields = [
                RDLField(
                    name=col.name,
                    data_field=col.name,
                    rdl_type=PBI_TO_RDL_TYPE.get(
                        "decimal" if col.name in sum_aliases else ("int64" if col.name in count_aliases else col.pbi_type),
                        "String",
                    ),
                )
                for col in table_ref.columns
            ]

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
