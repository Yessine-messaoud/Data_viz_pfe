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
    VisualEncoding,
    Worksheet,
)
from viz_agent.phase1_parser.column_decoder import decode_column_ref
from viz_agent.phase1_parser.dashboard_zone_mapper import extract_dashboard_worksheets
from viz_agent.phase1_parser.pre_semantic_enricher import PreSemanticEnricher
from viz_agent.phase1_parser.visual_type_mapper import resolve_visual_mapping


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
        relationships = self._parse_tableau_relationships(twb_root)

        parsed = ParsedWorkbook(
            worksheets=worksheets,
            datasources=datasources,
            dashboards=dashboards,
            calculated_fields=calc_fields,
            parameters=parameters,
            filters=filters,
            color_palettes=palettes,
            tableau_relationships=relationships,
            data_registry=registry,
        )
        return PreSemanticEnricher().enrich(parsed, registry)

    def _parse_tableau_relationships(self, root: etree._Element) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []
        for relation in root.findall(".//relation"):
            left_table = ""
            right_table = ""

            child_relations = relation.findall("./relation")
            if len(child_relations) >= 2:
                left_table = self._relation_table_name(child_relations[0])
                right_table = self._relation_table_name(child_relations[1])

            if not left_table:
                left_table = self._relation_table_name(relation, keys=("left", "left-table", "left_table", "table"))
            if not right_table:
                right_table = self._relation_table_name(relation, keys=("right", "right-table", "right_table"))

            clause_text = ""
            clause = relation.find(".//clause")
            if clause is not None:
                clause_text = str(clause.get("expression", "") or clause.get("formula", "") or "").strip()

            left_col, right_col = self._extract_join_columns(clause_text)
            if not left_table or not right_table:
                continue

            join_type = str(relation.get("join", relation.get("type", "INNER")) or "INNER").strip().upper()
            if join_type == "JOIN":
                join_type = "INNER"
            if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
                join_type = "INNER"

            source_xml_ref = clause_text or str(relation.get("name", "") or relation.get("table", "") or "").strip()
            relationships.append(
                {
                    "left_table": left_table,
                    "right_table": right_table,
                    "left_col": left_col,
                    "right_col": right_col,
                    "type": join_type,
                    "source_xml_ref": source_xml_ref,
                }
            )

        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for rel in relationships:
            key = (
                str(rel.get("left_table", "")).strip().lower(),
                str(rel.get("right_table", "")).strip().lower(),
                str(rel.get("left_col", "")).strip().lower(),
                str(rel.get("right_col", "")).strip().lower(),
                str(rel.get("type", "INNER")).strip().upper(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(rel)

        return deduped

    def _relation_table_name(self, node: etree._Element, keys: tuple[str, ...] = ("table", "name", "caption")) -> str:
        for key in keys:
            value = str(node.get(key, "") or "").strip()
            if value:
                return value
        return ""

    def _extract_join_columns(self, clause_text: str) -> tuple[str, str]:
        text = str(clause_text or "")
        if not text:
            return "id", "id"

        match = re.search(
            r"\[([^\]]+)\]\.\[([^\]]+)\]\s*=\s*\[([^\]]+)\]\.\[([^\]]+)\]",
            text,
        )
        if match:
            return match.group(2).strip(), match.group(4).strip()

        quoted = re.search(
            r'"([^\"]+)"\."([^\"]+)"\s*=\s*"([^\"]+)"\."([^\"]+)"',
            text,
        )
        if quoted:
            return quoted.group(2).strip(), quoted.group(4).strip()

        return "id", "id"

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
            datasource_name = self._worksheet_datasource_name(ws)
            worksheet_title = self._worksheet_title(ws, name)

            rows_shelf = self._extract_shelf_columns(ws.findtext(".//rows"), datasource_name)
            cols_shelf = self._extract_shelf_columns(ws.findtext(".//cols"), datasource_name)
            marks_shelf, mark_encodings = self._extract_marks_columns(ws, datasource_name)
            raw_mark_type = self._worksheet_mark_type(ws)
            mark_type = self._infer_mark_type(name, raw_mark_type, rows_shelf, cols_shelf, marks_shelf, mark_encodings)

            worksheets.append(
                Worksheet(
                    name=name,
                    title=worksheet_title,
                    mark_type=mark_type,
                    raw_mark_type=raw_mark_type,
                    datasource_name=datasource_name,
                    rows_shelf=rows_shelf,
                    cols_shelf=cols_shelf,
                    marks_shelf=marks_shelf,
                    mark_encodings=mark_encodings,
                )
            )
        return worksheets

    def _worksheet_mark_type(self, worksheet_xml: etree._Element) -> str:
        mark_node = worksheet_xml.find(".//mark")
        return mark_node.get("class", "Text") if mark_node is not None else "Text"

    def _infer_mark_type(
        self,
        worksheet_name: str,
        raw_mark_type: str,
        rows_shelf: list,
        cols_shelf: list,
        marks_shelf: list,
        mark_encodings: dict[str, object],
    ) -> str:
        encoding = VisualEncoding(
            x=cols_shelf[0].column if cols_shelf else None,
            y=rows_shelf[0].column if rows_shelf else None,
            color=self._mark_column(mark_encodings, marks_shelf, "color", 0),
            size=self._mark_column(mark_encodings, marks_shelf, "size", 1),
            detail=self._mark_column(mark_encodings, marks_shelf, "detail", 2),
        )
        resolution = resolve_visual_mapping(worksheet_name, raw_mark_type, encoding)
        logical_to_mark = {
            "bar": "Bar",
            "line": "Line",
            "pie": "Pie",
            "treemap": "Treemap",
            "scatter": "Circle",
            "map": "Map",
            "table": "Text",
            "kpi": "Text",
            "gantt": "Gantt",
        }
        return logical_to_mark.get(resolution.logical_type, "Text")

    def _worksheet_title(self, worksheet_xml: etree._Element, fallback_name: str) -> str:
        runs = worksheet_xml.findall(".//layout-options/title/formatted-text/run")
        if not runs:
            return fallback_name
        text = "".join((run.text or "") for run in runs).strip()
        if not text:
            return fallback_name
        return text.replace("\r", "").replace("\n", " ").strip()

    def _extract_shelf_columns(self, shelf_text: str | None, default_table: str) -> list:
        if not shelf_text:
            return []
        # Capture tokens like [federated.0data1].[sum:TotalSales:qk]
        tokens = re.findall(r"\[[^\]]+\]\.\[[^\]]+\]", shelf_text)
        return [decode_column_ref(token, default_table=default_table) for token in tokens]

    def _extract_marks_columns(self, worksheet_xml: etree._Element, default_table: str) -> tuple[list, dict[str, object]]:
        marks: list = []
        mark_encodings: dict[str, object] = {}
        for encoding_name in ("color", "size", "detail", "text", "shape"):
            for encoding_node in worksheet_xml.findall(f".//encodings/{encoding_name}"):
                column = encoding_node.get("column", "")
                if column:
                    ref = decode_column_ref(column, default_table=default_table)
                    marks.append(ref)
                    if encoding_name in {"color", "size", "detail"} and encoding_name not in mark_encodings:
                        mark_encodings[encoding_name] = ref

        if not marks:
            # Some TWB files store mark encoding as column-instance definitions.
            for column_instance in worksheet_xml.findall(".//datasource-dependencies/column-instance"):
                column = column_instance.get("column", "")
                if column:
                    marks.append(decode_column_ref(column, default_table=default_table))
        return marks, mark_encodings

    def _mark_column(
        self,
        mark_encodings: dict[str, object],
        marks_shelf: list,
        role: str,
        fallback_index: int,
    ) -> str | None:
        if mark_encodings:
            ref = mark_encodings.get(role)
            if ref is None:
                return None
            column = str(getattr(ref, "column", "") or "").strip()
            return column or None

        ref = mark_encodings.get(role)
        if ref is not None:
            column = str(getattr(ref, "column", "") or "").strip()
            return column or None
        if len(marks_shelf) > fallback_index:
            column = str(getattr(marks_shelf[fallback_index], "column", "") or "").strip()
            return column or None
        return None

    def _worksheet_datasource_name(self, worksheet_xml: etree._Element) -> str:
        ds_node = worksheet_xml.find(".//datasource")
        if ds_node is None:
            return ""
        return ds_node.get("name", "") or ds_node.get("caption", "")

    def _parse_datasources(self, root: etree._Element) -> list[DataSource]:
        datasources_by_name: dict[str, DataSource] = {}
        for ds in root.findall(".//datasource"):
            columns = []
            seen_column_names: set[str] = set()
            ds_name = ds.get("name", "")
            if not ds_name:
                continue
            dependencies = root.findall(f".//datasource-dependencies[@datasource='{ds_name}']/column")
            for column in dependencies:
                raw_name = column.get("name", "")
                col_name = raw_name.strip("[]") if raw_name else ""
                if not col_name:
                    continue
                norm_col_name = col_name.lower()
                if norm_col_name in seen_column_names:
                    continue
                seen_column_names.add(norm_col_name)
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

            connection_type = ds.find(".//connection").get("class", "") if ds.find(".//connection") is not None else ""
            current = DataSource(
                name=ds_name,
                caption=ds.get("caption", ""),
                connection_type=connection_type,
                columns=columns,
            )

            existing = datasources_by_name.get(ds_name)
            if existing is None:
                datasources_by_name[ds_name] = current
                continue

            # Merge duplicate datasource nodes (frequent in TWB/TWBX) while keeping unique columns.
            seen_cols = {str(col.name).lower() for col in existing.columns}
            for col in current.columns:
                col_name = str(col.name).strip()
                if not col_name:
                    continue
                norm_name = col_name.lower()
                if norm_name in seen_cols:
                    continue
                existing.columns.append(col)
                seen_cols.add(norm_name)

            if not existing.caption and current.caption:
                existing.caption = current.caption
            if not existing.connection_type and current.connection_type:
                existing.connection_type = current.connection_type

        return list(datasources_by_name.values())

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
            raw_column = str(filt.get("column", "") or "").strip()
            decoded = decode_column_ref(raw_column, default_table="")
            business_field = str(getattr(decoded, "column", "") or "").strip() or raw_column or "unknown"
            parsed_filters.append(
                Filter(
                    field=business_field,
                    operator=filt.get("op", "="),
                    value=filt.get("value"),
                    column=business_field,
                )
            )
        return parsed_filters

    def _parse_palettes(self, root: etree._Element) -> list[Palette]:
        palettes: list[Palette] = []
        for color_palette in root.findall(".//color-palette"):
            colors = [color.get("value", "") for color in color_palette.findall(".//color") if color.get("value")]
            palettes.append(Palette(name=color_palette.get("name", "palette"), colors=colors))
        return palettes
