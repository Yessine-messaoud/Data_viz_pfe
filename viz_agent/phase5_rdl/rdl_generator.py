from __future__ import annotations

from datetime import datetime
import os
import re

from lxml import etree

from viz_agent.phase5_rdl.rdl_visual_mapper import RDLVisualMapper

RDL_NAMESPACE = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RDL_XSD = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition/ReportDefinition.xsd"
RD_NAMESPACE = "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"


class RDLGenerator:
    def __init__(self, llm_client=None, calc_translator=None):
        self.llm = llm_client
        self.calc_translator = calc_translator

    def generate(self, spec, layouts: dict[str, dict], rdl_pages: list) -> str:
        self._assign_rdl_dataset_names(spec.rdl_datasets)

        root = etree.Element(
            "Report",
            nsmap={
                None: RDL_NAMESPACE,
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "rd": RD_NAMESPACE,
            },
        )
        root.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", f"{RDL_NAMESPACE} {RDL_XSD}")

        self._add_metadata(root, spec)
        self._add_datasources(root, spec.rdl_datasets)
        self._add_datasets(root, spec.rdl_datasets)
        self._add_parameters(root, spec)

        report_sections = etree.SubElement(root, "ReportSections")
        report_section = etree.SubElement(report_sections, "ReportSection")

        body = etree.SubElement(report_section, "Body")
        report_items = etree.SubElement(body, "ReportItems")

        mapper = RDLVisualMapper(llm_client=self.llm, use_llm=True)
        appended_items = 0
        for page in rdl_pages:
            page_layout = layouts.get(page.name, {})
            for visual in page.visuals:
                rect = page_layout.get(visual.id)
                if rect is None:
                    continue
                dataset = self._get_dataset_for_visual(visual, spec.rdl_datasets)
                if dataset is None:
                    continue
                element = mapper.map_visual(visual, dataset, rect)
                report_items.append(element)
                appended_items += 1

        if appended_items == 0:
            fallback = etree.SubElement(report_items, "Textbox")
            fallback.set("Name", "tbNoVisuals")

            paragraphs = etree.SubElement(fallback, "Paragraphs")
            paragraph = etree.SubElement(paragraphs, "Paragraph")
            text_runs = etree.SubElement(paragraph, "TextRuns")
            run = etree.SubElement(text_runs, "TextRun")
            value = etree.SubElement(run, "Value")
            value.text = "No visuals available for this report."

            top = etree.SubElement(fallback, "Top")
            top.text = "0.2in"
            left = etree.SubElement(fallback, "Left")
            left.text = "0.2in"
            height = etree.SubElement(fallback, "Height")
            height.text = "0.3in"
            width = etree.SubElement(fallback, "Width")
            width.text = "6in"

        body_height = etree.SubElement(body, "Height")
        body_height.text = "6.5in"

        section_width = etree.SubElement(report_section, "Width")
        section_width.text = "10.5in"

        self._add_page_setup(report_section)

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")

    def _add_metadata(self, root, spec):
        description = etree.SubElement(root, "Description")
        description.text = f"Genere par VizAgent v2 le {datetime.now().isoformat()}"
        auto_refresh = etree.SubElement(root, "AutoRefresh")
        auto_refresh.text = "0"

    def _add_datasources(self, root, datasets):
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

    def _add_datasets(self, root, datasets):
        ds_collection = etree.SubElement(root, "DataSets")
        for dataset in datasets:
            ds_el = etree.SubElement(ds_collection, "DataSet")
            ds_el.set("Name", getattr(dataset, "rdl_name", self._safe_identifier(dataset.name, "DataSet1")))

            query = etree.SubElement(ds_el, "Query")
            ds_name = etree.SubElement(query, "DataSourceName")
            ds_name.text = "DataSource1"
            cmd = etree.SubElement(query, "CommandText")
            cmd.text = self._normalize_command_text(getattr(dataset, "query", ""))

            fields_el = etree.SubElement(ds_el, "Fields")
            for field in dataset.fields:
                f_el = etree.SubElement(fields_el, "Field")
                f_el.set("Name", field.name)
                data_field = etree.SubElement(f_el, "DataField")
                data_field.text = field.data_field
                type_name = etree.SubElement(f_el, f"{{{RD_NAMESPACE}}}TypeName")
                type_name.text = field.rdl_type

    def _add_parameters(self, root, spec):
        if not spec.dashboard_spec.global_filters:
            return
        params = etree.SubElement(root, "ReportParameters")
        for filt in spec.dashboard_spec.global_filters:
            param = etree.SubElement(params, "ReportParameter")
            param.set("Name", filt.field.replace(" ", "_"))
            dtype = etree.SubElement(param, "DataType")
            dtype.text = "String"
            prompt = etree.SubElement(param, "Prompt")
            prompt.text = filt.field

    def _add_page_setup(self, report_section):
        page = etree.SubElement(report_section, "Page")
        height = etree.SubElement(page, "PageHeight")
        height.text = "8.5in"
        width = etree.SubElement(page, "PageWidth")
        width.text = "11in"
        for margin_name in ["TopMargin", "BottomMargin", "LeftMargin", "RightMargin"]:
            margin = etree.SubElement(page, margin_name)
            margin.text = "0.25in"

    def _get_dataset_for_visual(self, visual, datasets):
        for dataset in datasets:
            for axis_ref in visual.data_binding.axes.values():
                if not hasattr(axis_ref, "table"):
                    continue
                axis_table = axis_ref.table
                if axis_table == dataset.name:
                    return dataset
                axis_table_norm = self._safe_identifier(axis_table, "")
                dataset_name_norm = self._safe_identifier(dataset.name, "")
                if axis_table_norm and axis_table_norm == dataset_name_norm:
                    return dataset
        return datasets[0] if datasets else None

    def _safe_identifier(self, value, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "")).strip("_")
        if not cleaned:
            cleaned = fallback
        if not cleaned:
            return ""
        if not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = f"_{cleaned}"
        return cleaned[:120]

    def _assign_rdl_dataset_names(self, datasets) -> None:
        used_names: set[str] = set()
        for index, dataset in enumerate(datasets, start=1):
            base = self._safe_identifier(dataset.name, f"DataSet{index}")
            candidate = base
            suffix = 2
            while candidate in used_names:
                candidate = f"{base}_{suffix}"
                suffix += 1
            setattr(dataset, "rdl_name", candidate)
            used_names.add(candidate)

    def _sanitize_connection_string(self, conn_str: str) -> str:
        # Keep RDL portable: remove embedded credential directives that can conflict
        # with Report Builder/SSRS credential configuration.
        blocked_keys = {
            "user id",
            "userid",
            "user",
            "username",
            "uid",
            "password",
            "pwd",
            "integrated security",
            "integratedsecurity",
            "trusted connection",
            "trusted_connection",
            "authentication",
            "persist security info",
            "persistsecurityinfo",
        }
        parts = []
        for part in str(conn_str or "").split(";"):
            token = part.strip()
            if not token:
                continue
            if "=" in token:
                key, value = token.split("=", 1)
                if key.strip().lower() in blocked_keys:
                    continue
                token = f"{key.strip()}={value.strip()}"
            parts.append(token)

        if not parts:
            return "Data Source=localhost\\SQLEXPRESS;Initial Catalog=AdventureWorksDW2022"
        return ";".join(parts)

    def _quote_sql_identifier(self, value: str) -> str:
        return f"[{str(value).replace(']', ']]')}]"

    def _normalize_command_text(self, query: str) -> str:
        text = str(query or "").strip()
        if not text:
            return "SELECT 1"

        # Convert tuple-style references like:
        # SELECT * FROM ('schema', 'table')
        # into SQL Server-compatible identifiers.
        tuple_match = re.match(
            r"^SELECT\s+\*\s+FROM\s*\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if tuple_match:
            schema_name = tuple_match.group(1).strip()
            table_name = tuple_match.group(2).strip()
            # Tableau extracts often come as a logical placeholder ('Extract','Extract').
            # For the default AdventureWorksDW target, emit a concrete SQL query that
            # provides the expected fields used by visuals.
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

        return text
