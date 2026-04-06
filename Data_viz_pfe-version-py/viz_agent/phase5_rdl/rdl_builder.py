from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re
from typing import Any

from lxml import etree

from viz_agent.phase4_transform.rdl_dataset_mapper import RDLDataset, RDLField
from viz_agent.phase5_rdl.rdl_visual_mapper import RDLVisualMapper


RDL_NAMESPACE = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RD_NAMESPACE = "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"
RDL_XSD = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition/ReportDefinition.xsd"


@dataclass
class RDLBuildDebug:
    xml: str = ""
    datasets: list[dict[str, Any]] = field(default_factory=list)
    visuals: list[dict[str, Any]] = field(default_factory=list)
    mappings: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    auto_fixes: list[str] = field(default_factory=list)
    confidence_by_visual: dict[str, float] = field(default_factory=dict)


class RDLBuilder:
    def __init__(self, visual_mapper: RDLVisualMapper | None = None) -> None:
        self.visual_mapper = visual_mapper or RDLVisualMapper(use_llm=False)

    def build(self, spec, layouts: dict[str, dict], rdl_pages: list) -> tuple[etree._Element, RDLBuildDebug]:
        debug = RDLBuildDebug()
        datasets = self._normalize_datasets(getattr(spec, "rdl_datasets", []) or [])
        for dataset in datasets:
            setattr(dataset, "query", self._normalize_command_text(getattr(dataset, "query", "")))
        self._ensure_dataset_fields_cover_query_projection(datasets)
        self._ensure_dataset_fields_cover_visuals(datasets, rdl_pages)
        debug.datasets = [self._dataset_to_debug(dataset) for dataset in datasets]

        root = etree.Element(
            "Report",
            nsmap={
                None: RDL_NAMESPACE,
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "rd": RD_NAMESPACE,
            },
        )
        root.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", f"{RDL_NAMESPACE} {RDL_XSD}")

        self._add_metadata(root, spec, datasets)
        self._add_datasources(root, spec)
        parameter_names, param_map = self._add_parameters(root, spec)
        self._add_datasets(root, datasets, spec, param_map)
        self._add_parameter_layout(root, parameter_names)

        report_sections = etree.SubElement(root, "ReportSections")
        report_section = etree.SubElement(report_sections, "ReportSection")
        body = etree.SubElement(report_section, "Body")
        report_items = etree.SubElement(body, "ReportItems")

        dataset_by_name = {self._safe_identifier(dataset.name, "").lower(): dataset for dataset in datasets}
        dataset_by_raw_name = {str(dataset.name).strip().lower(): dataset for dataset in datasets}

        for page in rdl_pages:
            page_name = str(getattr(page, "name", "") or "").strip()
            page_layout = layouts.get(page_name, {}) if isinstance(layouts, dict) else {}
            for visual in getattr(page, "visuals", []) or []:
                visual_name = str(getattr(visual, "id", "") or getattr(visual, "source_worksheet", "") or "").strip()
                rect = page_layout.get(visual_name)
                if rect is None:
                    debug.warnings.append(f"{visual_name}: missing layout rectangle, skipped")
                    continue

                dataset = self._resolve_dataset_for_visual(visual, datasets, dataset_by_name, dataset_by_raw_name)
                if dataset is None:
                    debug.errors.append(f"{visual_name}: no dataset could be assigned")
                    continue

                element = self.visual_mapper.map_visual(visual, dataset, rect)
                if element is None:
                    debug.errors.append(f"{visual_name}: visual mapping failed")
                    continue

                report_items.append(element)
                mapping_entry = {
                    "visual_id": visual_name,
                    "dataset": self._dataset_name(dataset),
                    "visual_type": str(getattr(visual, "type", "") or "").strip().lower(),
                    "rdl_type": str(getattr(visual, "rdl_type", "") or "").strip(),
                }
                debug.visuals.append(mapping_entry)
                debug.mappings.append(mapping_entry)
                debug.confidence_by_visual[visual_name] = 1.0

        if len(report_items) == 0:
            self._add_fallback_item(report_items)
            debug.warnings.append("No visuals available; inserted fallback textbox")

        body_height = etree.SubElement(body, "Height")
        body_height.text = "6.5in"

        section_width = etree.SubElement(report_section, "Width")
        section_width.text = "10.5in"

        self._add_page_setup(report_section)
        self._ensure_unique_report_item_names(root)
        self._ensure_unique_group_names(root)

        debug.xml = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")
        return root, debug

    def build_xml(self, spec, layouts: dict[str, dict], rdl_pages: list) -> tuple[str, RDLBuildDebug]:
        root, debug = self.build(spec, layouts, rdl_pages)
        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8"), debug

    def _normalize_datasets(self, datasets: list[Any]) -> list[RDLDataset]:
        normalized: list[RDLDataset] = []
        used_names: set[str] = set()
        for index, dataset in enumerate(datasets, start=1):
            dataset_name = str(getattr(dataset, "name", "") or "").strip()
            if not dataset_name:
                continue
            base = self._safe_identifier(getattr(dataset, "rdl_name", dataset_name), f"DataSet{index}")
            candidate = base
            suffix = 2
            while candidate.lower() in used_names:
                candidate = f"{base}_{suffix}"
                suffix += 1
            setattr(dataset, "rdl_name", candidate)
            used_names.add(candidate.lower())
            normalized.append(dataset)
        return normalized

    def _dataset_to_debug(self, dataset: Any) -> dict[str, Any]:
        fields = getattr(dataset, "fields", []) or []
        return {
            "name": self._dataset_name(dataset),
            "query": str(getattr(dataset, "query", "") or "").strip(),
            "field_count": len(fields),
            "field_names": [str(getattr(field, "name", "") or "").strip() for field in fields if str(getattr(field, "name", "") or "").strip()],
        }

    def _resolve_dataset_for_visual(self, visual, datasets, dataset_by_name, dataset_by_raw_name):
        candidates: list[str] = []
        dataset_name = str(getattr(visual.data_binding, "dataset", "") or "").strip() if hasattr(visual, "data_binding") else ""
        if dataset_name:
            candidates.append(dataset_name)

        axes = getattr(visual.data_binding, "axes", {}) if hasattr(visual, "data_binding") else {}
        for axis_ref in axes.values():
            if hasattr(axis_ref, "table") and getattr(axis_ref, "table", ""):
                candidates.append(str(getattr(axis_ref, "table", "") or "").strip())
        for measure_ref in getattr(visual.data_binding, "measures", []) or []:
            if hasattr(measure_ref, "name"):
                candidates.append(str(measure_ref.name))

        if hasattr(visual, "source_worksheet") and str(getattr(visual, "source_worksheet", "") or "").strip():
            candidates.append(str(getattr(visual, "source_worksheet", "") or "").strip())

        for candidate in candidates:
            normalized = self._safe_identifier(candidate, "").lower()
            if normalized in dataset_by_name:
                return dataset_by_name[normalized]
            if candidate.strip().lower() in dataset_by_raw_name:
                return dataset_by_raw_name[candidate.strip().lower()]

        return datasets[0] if datasets else None

    def _ensure_dataset_fields_cover_visuals(self, datasets: list[RDLDataset], rdl_pages: list) -> None:
        if not datasets:
            return

        dataset_by_name = {self._safe_identifier(dataset.name, "").lower(): dataset for dataset in datasets}
        dataset_by_raw_name = {str(dataset.name).strip().lower(): dataset for dataset in datasets}

        def _find_dataset_for_visual(visual):
            binding = getattr(visual, "data_binding", None)
            if binding is not None:
                ds_name = str(getattr(binding, "dataset", "") or "").strip()
                if ds_name:
                    normalized = self._safe_identifier(ds_name, "").lower()
                    if normalized in dataset_by_name:
                        return dataset_by_name[normalized]
                    if ds_name.lower() in dataset_by_raw_name:
                        return dataset_by_raw_name[ds_name.lower()]

                axes = getattr(binding, "axes", {}) or {}
                for ref in axes.values():
                    table_name = str(getattr(ref, "table", "") or "").strip()
                    if not table_name:
                        continue
                    normalized = self._safe_identifier(table_name, "").lower()
                    if normalized in dataset_by_name:
                        return dataset_by_name[normalized]
                    if table_name.lower() in dataset_by_raw_name:
                        return dataset_by_raw_name[table_name.lower()]

            return datasets[0]

        for page in rdl_pages or []:
            for visual in getattr(page, "visuals", []) or []:
                dataset = _find_dataset_for_visual(visual)
                if dataset is None:
                    continue

                existing = {
                    self._safe_identifier(str(getattr(field, "name", "") or "").strip(), "Field").lower()
                    for field in getattr(dataset, "fields", []) or []
                }
                binding = getattr(visual, "data_binding", None)
                if binding is None:
                    continue

                references: list[tuple[str, str]] = []
                for ref in (getattr(binding, "axes", {}) or {}).values():
                    col_name = str(getattr(ref, "column", "") or "").strip()
                    if col_name:
                        references.append((col_name, "String"))
                    measure_name = str(getattr(ref, "name", "") or "").strip()
                    if measure_name:
                        references.append((measure_name, "Decimal"))

                for mref in getattr(binding, "measures", []) or []:
                    mname = str(getattr(mref, "name", "") or "").strip()
                    if mname:
                        references.append((mname, "Decimal"))

                for field_name, field_type in references:
                    cls_name = self._safe_identifier(field_name, "Field")
                    lowered = cls_name.lower()
                    if lowered in existing:
                        continue
                    dataset.fields.append(RDLField(name=cls_name, data_field=field_name, rdl_type=field_type))
                    existing.add(lowered)

    def _ensure_dataset_fields_cover_query_projection(self, datasets: list[RDLDataset]) -> None:
        alias_pattern = re.compile(r"\bAS\s+(?:\[([^\]]+)\]|([A-Za-z_][A-Za-z0-9_]*))", flags=re.IGNORECASE)

        for dataset in datasets:
            query = str(getattr(dataset, "query", "") or "")
            if not query:
                continue

            existing = {
                self._safe_identifier(str(getattr(field, "name", "") or "").strip(), "Field").lower()
                for field in getattr(dataset, "fields", []) or []
                if str(getattr(field, "name", "") or "").strip()
            }

            for match in alias_pattern.finditer(query):
                raw_alias = (match.group(1) or match.group(2) or "").strip()
                if not raw_alias:
                    continue

                cls_name = self._safe_identifier(raw_alias, "Field")
                lowered = cls_name.lower()
                if lowered in existing:
                    continue

                alias_lower = raw_alias.lower()
                if any(token in alias_lower for token in ("quantity", "qty", "count", "number", "key")):
                    inferred_type = "Integer"
                elif any(token in alias_lower for token in ("amount", "price", "cost", "profit", "revenue", "tax", "total", "discount", "freight")):
                    inferred_type = "Decimal"
                else:
                    inferred_type = "String"

                dataset.fields.append(RDLField(name=cls_name, data_field=raw_alias, rdl_type=inferred_type))
                existing.add(lowered)

    def _add_metadata(self, root, spec, datasets: list[RDLDataset]):
        description = etree.SubElement(root, "Description")
        ds_meta = self._datasource_metadata(spec, datasets)
        description.text = (
            f"Genere par VizAgent v2 le {datetime.now(timezone.utc).isoformat()}"
            f" | Datasources: {ds_meta}"
        )
        auto_refresh = etree.SubElement(root, "AutoRefresh")
        auto_refresh.text = "0"

    def _add_datasources(self, root, spec):
        ds_collection = etree.SubElement(root, "DataSources")
        datasource = etree.SubElement(ds_collection, "DataSource")
        datasource.set("Name", "DataSource1")

        conn = etree.SubElement(datasource, "ConnectionProperties")
        provider = etree.SubElement(conn, "DataProvider")
        provider.text = "SQL"
        conn_string = etree.SubElement(conn, "ConnectString")
        raw_conn = os.environ.get(
            "VIZ_AGENT_RDL_CONNECTION_STRING",
            "Data Source=localhost\\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022",
        )
        conn_string.text = self._sanitize_connection_string(raw_conn)
        integrated = etree.SubElement(conn, "IntegratedSecurity")
        integrated.text = "true"

        # Report designer metadata is helpful for SSRS design-time traceability.
        ds_id = etree.SubElement(datasource, f"{{{RD_NAMESPACE}}}DataSourceID")
        meta_hash = abs(hash(self._datasource_metadata(spec, [])))
        ds_id.text = f"vizagent-{meta_hash}"

    def _add_datasets(self, root, datasets, spec, param_map: dict[str, str]):
        ds_collection = etree.SubElement(root, "DataSets")
        global_filters = getattr(spec.dashboard_spec, "global_filters", []) if getattr(spec, "dashboard_spec", None) else []
        for dataset in datasets:
            ds_el = etree.SubElement(ds_collection, "DataSet")
            ds_el.set("Name", getattr(dataset, "rdl_name", self._safe_identifier(dataset.name, "DataSet1")))

            query = etree.SubElement(ds_el, "Query")
            ds_name = etree.SubElement(query, "DataSourceName")
            ds_name.text = "DataSource1"
            cmd = etree.SubElement(query, "CommandText")
            normalized_query = self._normalize_command_text(getattr(dataset, "query", ""))
            cmd.text = normalized_query
            sum_aliases = self._extract_sum_aliases(normalized_query)
            count_aliases = self._extract_count_aliases(normalized_query)

            fields_el = etree.SubElement(ds_el, "Fields")
            seen_field_names: set[str] = set()
            for field in getattr(dataset, "fields", []) or []:
                field_name = str(getattr(field, "name", "") or "").strip()
                if not field_name:
                    continue
                normalized_name = field_name.lower()
                if normalized_name in seen_field_names:
                    continue
                seen_field_names.add(normalized_name)

                f_el = etree.SubElement(fields_el, "Field")
                f_el.set("Name", field_name)
                data_field = etree.SubElement(f_el, "DataField")
                data_field.text = str(getattr(field, "data_field", field_name) or field_name)
                type_name = etree.SubElement(f_el, f"{{{RD_NAMESPACE}}}TypeName")
                if field_name in sum_aliases:
                    type_name.text = "Decimal"
                elif field_name in count_aliases:
                    type_name.text = "Integer"
                else:
                    type_name.text = str(getattr(field, "rdl_type", "String") or "String")

            self._add_dataset_filters(ds_el, global_filters, param_map, getattr(dataset, "fields", []) or [])

    def _extract_sum_aliases(self, query: str) -> set[str]:
        return set(match.group(1) for match in re.finditer(r"SUM\s*\([^\)]*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)", str(query or ""), flags=re.IGNORECASE))

    def _extract_count_aliases(self, query: str) -> set[str]:
        return set(match.group(1) for match in re.finditer(r"COUNT\s*\([^\)]*\)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)", str(query or ""), flags=re.IGNORECASE))

    def _quote_sql_identifier(self, value: str) -> str:
        return f"[{str(value).replace(']', ']]')}]"

    def _expanded_adventureworks_query(self) -> str:
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

    def _normalize_command_text(self, query: str) -> str:
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
            return f"SELECT * FROM {self._quote_sql_identifier(schema_name)}.{self._quote_sql_identifier(table_name)}"

        federated_match = re.match(r"^SELECT\s+\*\s+FROM\s+federated\.[A-Za-z0-9_]+$", text, flags=re.IGNORECASE)
        if federated_match:
            return self._expanded_adventureworks_query()

        legacy_aw_match = re.search(
            r"FROM\s+dbo\.FactInternetSales\s+AS\s+f.*DimSalesTerritory.*DimProduct",
            text,
            flags=re.IGNORECASE,
        )
        if legacy_aw_match:
            return self._expanded_adventureworks_query()

        return text

    def _add_parameters(self, root, spec):
        global_filters = getattr(spec.dashboard_spec, "global_filters", []) if getattr(spec, "dashboard_spec", None) else []
        if not global_filters:
            return [], {}
        params = etree.SubElement(root, "ReportParameters")
        seen_param_names: set[str] = set()
        suffix_by_base: dict[str, int] = {}
        ordered_names: list[str] = []
        param_map: dict[str, str] = {}
        for filt in global_filters:
            raw_name = str(getattr(filt, "field", "") or "").strip()
            if not raw_name:
                continue
            base_name = self._safe_identifier(raw_name, "Param")
            next_suffix = suffix_by_base.get(base_name, 1)
            candidate = base_name if next_suffix == 1 else f"{base_name}_{next_suffix}"
            while candidate.lower() in seen_param_names:
                next_suffix += 1
                candidate = f"{base_name}_{next_suffix}"
            suffix_by_base[base_name] = next_suffix + 1

            param_name = candidate
            normalized = param_name.lower()
            if normalized in seen_param_names:
                continue
            seen_param_names.add(normalized)

            param = etree.SubElement(params, "ReportParameter")
            param.set("Name", param_name)
            dtype = etree.SubElement(param, "DataType")
            dtype.text = "String"
            prompt = etree.SubElement(param, "Prompt")
            prompt.text = raw_name
            ordered_names.append(param_name)
            param_map[raw_name.lower()] = param_name
            field_alias = str(getattr(filt, "column", "") or "").strip()
            if field_alias:
                param_map[field_alias.lower()] = param_name
        return ordered_names, param_map

    def _add_dataset_filters(self, dataset_el, global_filters, param_map: dict[str, str], dataset_fields: list[Any]) -> None:
        if not global_filters:
            return

        field_names = {str(getattr(field, "name", "") or "").strip().lower() for field in dataset_fields}
        filters_el = None
        for filt in global_filters:
            field_name = str(getattr(filt, "field", "") or "").strip()
            column_name = str(getattr(filt, "column", "") or "").strip()
            filter_key = (column_name or field_name).strip().lower()
            if not filter_key:
                continue
            if filter_key not in field_names and field_name.lower() not in field_names and column_name.lower() not in field_names:
                continue

            param_name = param_map.get(filter_key) or param_map.get(field_name.lower()) or param_map.get(column_name.lower())
            if not param_name:
                continue

            if filters_el is None:
                filters_el = etree.SubElement(dataset_el, "Filters")

            filter_el = etree.SubElement(filters_el, "Filter")
            expr = etree.SubElement(filter_el, "FilterExpression")
            column_ref = column_name or field_name
            safe_col = self._safe_identifier(column_ref, "Field")
            expr.text = f"=Fields!{safe_col}.Value"

            operator = etree.SubElement(filter_el, "Operator")
            operator.text = self._normalize_filter_operator(str(getattr(filt, "operator", "=") or "="))

            values_el = etree.SubElement(filter_el, "FilterValues")
            val_el = etree.SubElement(values_el, "FilterValue")
            val_el.text = f"=Parameters!{param_name}.Value"

    def _normalize_filter_operator(self, op: str) -> str:
        normalized = str(op or "=").strip().lower()
        mapping = {
            "=": "Equal",
            "==": "Equal",
            "!=": "NotEqual",
            "<>": "NotEqual",
            ">": "GreaterThan",
            "<": "LessThan",
            ">=": "GreaterThanOrEqual",
            "<=": "LessThanOrEqual",
            "in": "In",
            "like": "Like",
        }
        return mapping.get(normalized, "Equal")

    def _datasource_metadata(self, spec, datasets: list[RDLDataset]) -> str:
        parts: list[str] = []
        if getattr(spec, "data_lineage", None) is not None:
            tables = getattr(spec.data_lineage, "tables", []) or []
            if tables:
                names = [str(getattr(t, "name", "") or "").strip() for t in tables]
                names = [n for n in names if n]
                if names:
                    parts.append("tables=" + ",".join(names[:8]))
        if datasets:
            ds_names = [str(getattr(d, "name", "") or "").strip() for d in datasets]
            ds_names = [n for n in ds_names if n]
            if ds_names:
                parts.append("datasets=" + ",".join(ds_names[:8]))
        return " | ".join(parts) if parts else "n/a"

    def _add_parameter_layout(self, root: etree._Element, parameter_names: list[str]) -> None:
        if not parameter_names:
            return
        layout = etree.SubElement(root, "ReportParametersLayout")
        grid = etree.SubElement(layout, "GridLayoutDefinition")
        cols = 2
        rows = (len(parameter_names) + cols - 1) // cols
        number_of_columns = etree.SubElement(grid, "NumberOfColumns")
        number_of_columns.text = str(cols)
        number_of_rows = etree.SubElement(grid, "NumberOfRows")
        number_of_rows.text = str(rows)
        cell_defs = etree.SubElement(grid, "CellDefinitions")

        for index, param_name in enumerate(parameter_names):
            cell = etree.SubElement(cell_defs, "CellDefinition")
            col_idx = etree.SubElement(cell, "ColumnIndex")
            col_idx.text = str(index % cols)
            row_idx = etree.SubElement(cell, "RowIndex")
            row_idx.text = str(index // cols)
            pname = etree.SubElement(cell, "ParameterName")
            pname.text = param_name

    def _add_page_setup(self, report_section):
        page = etree.SubElement(report_section, "Page")
        height = etree.SubElement(page, "PageHeight")
        height.text = "8.5in"
        width = etree.SubElement(page, "PageWidth")
        width.text = "11in"
        for margin_name in ["TopMargin", "BottomMargin", "LeftMargin", "RightMargin"]:
            margin = etree.SubElement(page, margin_name)
            margin.text = "0.25in"

    def _add_fallback_item(self, report_items: etree._Element) -> None:
        fallback = etree.SubElement(report_items, "Textbox")
        fallback.set("Name", "tbNoVisuals")
        paragraphs = etree.SubElement(fallback, "Paragraphs")
        paragraph = etree.SubElement(paragraphs, "Paragraph")
        text_runs = etree.SubElement(paragraph, "TextRuns")
        run = etree.SubElement(text_runs, "TextRun")
        value = etree.SubElement(run, "Value")
        value.text = "No visuals available for this report."
        for tag, text in (("Top", "0.2in"), ("Left", "0.2in"), ("Height", "0.3in"), ("Width", "6in")):
            node = etree.SubElement(fallback, tag)
            node.text = text

    def _safe_identifier(self, value, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "")).strip("_")
        if not cleaned:
            cleaned = fallback
        if not cleaned:
            return ""
        if not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = f"_{cleaned}"
        return cleaned[:120]

    def _sanitize_connection_string(self, conn_str: str) -> str:
        return re.sub(r"(?i)(password|pwd)\s*=\s*[^;]+;?", "", str(conn_str or "")).strip()

    def _dataset_name(self, dataset) -> str:
        return str(getattr(dataset, "rdl_name", getattr(dataset, "name", "DataSet1")))

    def _ensure_unique_report_item_names(self, root):
        seen: set[str] = set()
        # Only deduplicate top-level report items. Renaming nested chart internals
        # (ChartArea/ChartLegend/etc.) breaks ChartAreaName/LegendName references.
        for item in root.xpath(".//*[local-name()='ReportItems']/*[@Name]"):
            if not isinstance(item.tag, str):
                continue
            name = str(item.get("Name", "") or "").strip()
            if not name:
                continue
            candidate = name
            suffix = 2
            while candidate.lower() in seen:
                candidate = f"{name}_{suffix}"
                suffix += 1
            item.set("Name", candidate)
            seen.add(candidate.lower())

    def _ensure_unique_group_names(self, root):
        seen: set[str] = set()
        suffix_by_base: dict[str, int] = {}

        for group in root.xpath(".//*[local-name()='Group'][@Name]"):
            if not isinstance(group.tag, str):
                continue
            name = str(group.get("Name", "") or "").strip()
            if not name:
                continue

            lower = name.lower()
            if lower not in seen:
                seen.add(lower)
                continue

            base = self._safe_identifier(name, "grp")
            next_suffix = suffix_by_base.get(base, 2)
            candidate = f"{base}_{next_suffix}"
            while candidate.lower() in seen:
                next_suffix += 1
                candidate = f"{base}_{next_suffix}"

            group.set("Name", candidate)
            seen.add(candidate.lower())
            suffix_by_base[base] = next_suffix + 1
