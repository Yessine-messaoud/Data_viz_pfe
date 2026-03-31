from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from viz_agent.models.abstract_spec import (
    CalcField,
    DataSource,
    Filter,
    Palette,
    Parameter,
    ParsedWorkbook,
    TableauDashboard,
    Worksheet,
)
from viz_agent.phase1_parser.column_decoder import decode_column_ref
from viz_agent.phase1_parser.dashboard_zone_mapper import extract_dashboard_worksheets


class TableauParser:
    def parse(self, tableau_path: str, registry) -> ParsedWorkbook:
        twb_root = self._load_twb_xml(tableau_path)

        worksheets = self._parse_worksheets(twb_root)
        datasources = self._parse_datasources(twb_root)
        dashboards = self._parse_dashboards(twb_root)
        calc_fields = self._parse_calc_fields(twb_root)
        parameters = self._parse_parameters(twb_root)
        filters = self._parse_filters(twb_root)
        palettes = self._parse_palettes(twb_root)

        return ParsedWorkbook(
            worksheets=worksheets,
            datasources=datasources,
            dashboards=dashboards,
            calculated_fields=calc_fields,
            parameters=parameters,
            filters=filters,
            color_palettes=palettes,
            data_registry=registry,
        )

    def _load_twb_xml(self, tableau_path: str) -> etree._Element:
        path = Path(tableau_path)
        parser = etree.XMLParser(recover=False)

        if path.suffix.lower() == ".twb":
            try:
                tree = etree.parse(str(path), parser)
            except etree.XMLSyntaxError as exc:
                raise ValueError(f"Invalid TWB XML: {exc}") from exc
            return tree.getroot()

        if path.suffix.lower() != ".twbx":
            raise ValueError(f"Unsupported Tableau format: {path.suffix}")

        with zipfile.ZipFile(path) as archive:
            twb_files = [name for name in archive.namelist() if name.endswith(".twb")]
            if not twb_files:
                raise ValueError("No .twb file found in TWBX")

            twb_name = twb_files[0]
            with tempfile.TemporaryDirectory() as temp_dir:
                archive.extract(twb_name, temp_dir)
                twb_path = Path(temp_dir) / twb_name
                try:
                    tree = etree.parse(str(twb_path), parser)
                except etree.XMLSyntaxError as exc:
                    raise ValueError(f"Invalid TWB XML: {exc}") from exc
                return tree.getroot()

    def _parse_worksheets(self, root: etree._Element) -> list[Worksheet]:
        worksheets: list[Worksheet] = []
        for ws in root.findall(".//worksheet"):
            name = ws.get("name", "UnnamedWorksheet")
            mark_node = ws.find(".//mark")
            mark_type = mark_node.get("class", "Text") if mark_node is not None else "Text"
            datasource_name = self._worksheet_datasource_name(ws)

            rows_shelf = self._extract_shelf_columns(ws.findtext(".//rows"), datasource_name)
            cols_shelf = self._extract_shelf_columns(ws.findtext(".//cols"), datasource_name)
            marks_shelf = self._extract_marks_columns(ws, datasource_name)

            worksheets.append(
                Worksheet(
                    name=name,
                    mark_type=mark_type,
                    datasource_name=datasource_name,
                    rows_shelf=rows_shelf,
                    cols_shelf=cols_shelf,
                    marks_shelf=marks_shelf,
                )
            )
        return worksheets

    def _extract_shelf_columns(self, shelf_text: str | None, default_table: str) -> list:
        if not shelf_text:
            return []
        # Capture tokens like [federated.0data1].[sum:TotalSales:qk]
        tokens = re.findall(r"\[[^\]]+\]\.\[[^\]]+\]", shelf_text)
        return [decode_column_ref(token, default_table=default_table) for token in tokens]

    def _extract_marks_columns(self, worksheet_xml: etree._Element, default_table: str) -> list:
        marks: list = []
        # Some TWB files store mark encoding as column-instance definitions.
        for column_instance in worksheet_xml.findall(".//datasource-dependencies/column-instance"):
            column = column_instance.get("column", "")
            if column:
                marks.append(decode_column_ref(column, default_table=default_table))
        return marks

    def _worksheet_datasource_name(self, worksheet_xml: etree._Element) -> str:
        ds_node = worksheet_xml.find(".//datasource")
        if ds_node is None:
            return ""
        return ds_node.get("name", "") or ds_node.get("caption", "")

    def _parse_datasources(self, root: etree._Element) -> list[DataSource]:
        datasources: list[DataSource] = []
        for ds in root.findall(".//datasource"):
            columns = []
            ds_name = ds.get("name", "")
            dependencies = root.findall(f".//datasource-dependencies[@datasource='{ds_name}']/column")
            for column in dependencies:
                raw_name = column.get("name", "")
                col_name = raw_name.strip("[]") if raw_name else ""
                if not col_name:
                    continue
                datatype = (column.get("datatype", "") or "").lower()
                role = (column.get("role", "") or "").lower()
                if role == "measure":
                    mapped_role = "measure"
                elif role == "dimension":
                    mapped_role = "dimension"
                else:
                    mapped_role = "measure" if datatype in {"integer", "real", "float", "double", "number"} else "dimension"

                columns.append(
                    {
                        "name": col_name,
                        "pbi_type": "decimal" if mapped_role == "measure" else "text",
                        "role": mapped_role,
                        "is_hidden": False,
                        "label": "",
                    }
                )

            datasources.append(
                DataSource(
                    name=ds_name,
                    caption=ds.get("caption", ""),
                    connection_type=(ds.find(".//connection").get("class", "") if ds.find(".//connection") is not None else ""),
                    columns=columns,
                )
            )
        return datasources

    def _parse_dashboards(self, root: etree._Element) -> list[TableauDashboard]:
        dashboards: list[TableauDashboard] = []
        for dashboard in root.findall(".//dashboard"):
            name = dashboard.get("name", "UnnamedDashboard")
            worksheets = extract_dashboard_worksheets(dashboard)
            dashboards.append(TableauDashboard(name=name, worksheets=worksheets))
        return dashboards

    def _parse_calc_fields(self, root: etree._Element) -> list[CalcField]:
        calcs: list[CalcField] = []
        for column in root.findall(".//column"):
            formula = column.get("formula")
            if formula:
                calcs.append(CalcField(name=column.get("name", "calculated_field"), expression=formula))
        return calcs

    def _parse_parameters(self, root: etree._Element) -> list[Parameter]:
        params: list[Parameter] = []
        for param in root.findall(".//parameter"):
            params.append(
                Parameter(
                    name=param.get("name", "parameter"),
                    data_type=param.get("datatype", "string"),
                    default_value=param.get("value", ""),
                )
            )
        return params

    def _parse_filters(self, root: etree._Element) -> list[Filter]:
        parsed_filters: list[Filter] = []
        for filt in root.findall(".//filter"):
            parsed_filters.append(
                Filter(
                    field=filt.get("column", "unknown"),
                    operator=filt.get("op", "="),
                    value=filt.get("value"),
                    column=filt.get("column", ""),
                )
            )
        return parsed_filters

    def _parse_palettes(self, root: etree._Element) -> list[Palette]:
        palettes: list[Palette] = []
        for color_palette in root.findall(".//color-palette"):
            colors = [color.get("value", "") for color in color_palette.findall(".//color") if color.get("value")]
            palettes.append(Palette(name=color_palette.get("name", "palette"), colors=colors))
        return palettes
