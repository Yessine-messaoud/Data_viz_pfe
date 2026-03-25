from __future__ import annotations

import copy
import json
import re

from lxml import etree


class RDLVisualMapper:
    def __init__(self, llm_client=None, use_llm: bool = True):
        self.llm = llm_client
        self.use_llm = use_llm

    def _safe_name(self, value: str, fallback: str) -> str:
        # RDL Name attributes must be XML-friendly and stable.
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "")).strip("_")
        if not cleaned:
            cleaned = fallback
        if not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = f"_{cleaned}"
        return cleaned[:120]

    def _dataset_name(self, dataset) -> str:
        return str(getattr(dataset, "rdl_name", getattr(dataset, "name", "DataSet1")))

    def map_visual(self, visual, dataset, rect):
        # Charts are generated with deterministic XML because free-form LLM chart XML
        # frequently breaks strict SSRS schema constraints.
        if visual.type == "chart":
            return self._build_chart(visual, dataset, rect)

        if self.use_llm and self.llm is not None:
            llm_element = self._build_with_llm(visual, dataset, rect)
            if llm_element is not None:
                return llm_element

        rdl_type = visual.type
        if rdl_type == "tablix":
            return self._build_tablix(visual, dataset, rect)
        if rdl_type == "textbox":
            return self._build_kpi_textbox(visual, dataset, rect)
        return self._build_tablix(visual, dataset, rect)

    def _apply_rect(self, element: etree._Element, rect) -> None:
        for attr, value in rect.to_rdl().items():
            sub = etree.SubElement(element, attr)
            sub.text = value

    def _build_with_llm(self, visual, dataset, rect):
        expected_tag = {
            "chart": "Chart",
            "tablix": "Tablix",
            "textbox": "Textbox",
        }.get(visual.type)
        if expected_tag is None:
            return None

        axes_payload = {}
        if hasattr(visual, "data_binding") and hasattr(visual.data_binding, "axes"):
            for axis, axis_ref in visual.data_binding.axes.items():
                if hasattr(axis_ref, "column"):
                    axes_payload[axis] = axis_ref.column
                elif hasattr(axis_ref, "name"):
                    axes_payload[axis] = axis_ref.name

        fields_payload = [getattr(field, "name", "") for field in getattr(dataset, "fields", [])]

        system_prompt = (
            "Tu es un expert SSRS RDL 2016. "
            "Genere un seul element XML RDL pour ReportItems, sans markdown. "
            "Le XML doit etre valide, minimal mais deserialisable."
        )
        user_prompt = (
            "Retourne un JSON strict avec la cle rdl_xml.\n"
            f"Type attendu: {expected_tag}\n"
            f"Visual id: {visual.id}\n"
            f"Titre: {visual.title}\n"
            f"Worksheet source: {visual.source_worksheet}\n"
            f"DataSetName: {self._dataset_name(dataset)}\n"
            f"Axes: {json.dumps(axes_payload, ensure_ascii=True)}\n"
            f"Fields dataset: {json.dumps(fields_payload, ensure_ascii=True)}\n"
            "Contraintes chart: inclure ChartCategoryHierarchy, ChartSeriesHierarchy, ChartData, ChartAreas.\n"
            "Contraintes tablix: inclure DataSetName, TablixBody, colonnes et lignes minimales.\n"
            "Contraintes textbox: inclure Paragraphs/Paragraph/TextRuns/TextRun/Value.\n"
            "Ne pas inclure Left/Top/Width/Height (injectees apres).\n"
            "Ne pas inclure XML declaration."
        )

        try:
            llm_response = self.llm.chat_json(system_prompt, user_prompt)
            xml_text = str(llm_response.get("rdl_xml", "")).strip()
            if not xml_text:
                return None
            if xml_text.startswith("```"):
                xml_text = xml_text.replace("```xml", "").replace("```", "").strip()

            element = etree.fromstring(xml_text.encode("utf-8"))
            if etree.QName(element).localname != expected_tag:
                return None

            self._normalize_visual_element(element, visual, dataset, rect, expected_tag)
            return element
        except Exception:
            return None

    def _normalize_visual_element(self, element, visual, dataset, rect, expected_tag: str) -> None:
        element.set("Name", self._safe_name(getattr(visual, "id", expected_tag.lower()), expected_tag.lower()))

        # Normalize geometry from computed layout.
        for attr in ["Left", "Top", "Width", "Height"]:
            for child in element.findall(attr):
                element.remove(child)
        self._apply_rect(element, rect)

        if expected_tag in {"Chart", "Tablix"}:
            ds_node = element.find("DataSetName")
            if ds_node is None:
                ds_node = etree.SubElement(element, "DataSetName")
            ds_node.text = self._dataset_name(dataset)

        if expected_tag == "Chart":
            self._ensure_chart_minimum(element, visual)

    def _ensure_chart_minimum(self, chart, visual) -> None:
        self._normalize_chart_hierarchy(chart, "ChartCategoryHierarchy")
        self._normalize_chart_hierarchy(chart, "ChartSeriesHierarchy")

        category_hierarchy = chart.find("ChartCategoryHierarchy")
        if category_hierarchy is None:
            category_hierarchy = etree.SubElement(chart, "ChartCategoryHierarchy")
        category_members = category_hierarchy.find("ChartMembers")
        if category_members is None:
            category_members = etree.SubElement(category_hierarchy, "ChartMembers")
        category_member = category_members.find("ChartMember")
        if category_member is None:
            category_member = etree.SubElement(category_members, "ChartMember")
        if category_member.find("Label") is None:
            category_label = etree.SubElement(category_member, "Label")
            axis_x = visual.data_binding.axes.get("x") if hasattr(visual.data_binding, "axes") else None
            if axis_x is not None and hasattr(axis_x, "column"):
                category_label.text = f"=Fields!{axis_x.column}.Value"
            else:
                category_label.text = "=\"Category\""

        series_hierarchy = chart.find("ChartSeriesHierarchy")
        if series_hierarchy is None:
            series_hierarchy = etree.SubElement(chart, "ChartSeriesHierarchy")
        series_members = series_hierarchy.find("ChartMembers")
        if series_members is None:
            series_members = etree.SubElement(series_hierarchy, "ChartMembers")
        if series_members.find("ChartMember") is None:
            etree.SubElement(series_members, "ChartMember")

        # SSRS requires a Label under every ChartMember, including nested members.
        for member in chart.findall(".//ChartCategoryHierarchy//ChartMember"):
            label = member.find("Label")
            if label is None:
                label = etree.SubElement(member, "Label")
            if label.text is None or not str(label.text).strip():
                label.text = "=\"Category\""

        for member in chart.findall(".//ChartSeriesHierarchy//ChartMember"):
            label = member.find("Label")
            if label is None:
                label = etree.SubElement(member, "Label")
            if label.text is None or not str(label.text).strip():
                label.text = "=\"Series\""

        chart_data = chart.find("ChartData")
        if chart_data is None:
            chart_data = etree.SubElement(chart, "ChartData")
        series_collection = chart_data.find("ChartSeriesCollection")
        if series_collection is None:
            series_collection = etree.SubElement(chart_data, "ChartSeriesCollection")
        chart_series = series_collection.find("ChartSeries")
        if chart_series is None:
            chart_series = etree.SubElement(series_collection, "ChartSeries")
            chart_series.set("Name", self._safe_name(f"series_{visual.id}", "series_1"))

        points = chart_series.find("ChartDataPoints")
        if points is None:
            points = etree.SubElement(chart_series, "ChartDataPoints")
        point = points.find("ChartDataPoint")
        if point is None:
            point = etree.SubElement(points, "ChartDataPoint")
        values = point.find("ChartDataPointValues")
        if values is None:
            values = etree.SubElement(point, "ChartDataPointValues")
        if values.find("Y") is None:
            y_val = etree.SubElement(values, "Y")
            axis_y = visual.data_binding.axes.get("y") if hasattr(visual.data_binding, "axes") else None
            if axis_y is not None and hasattr(axis_y, "column"):
                y_val.text = f"=Sum(Fields!{axis_y.column}.Value)"
            else:
                y_val.text = "=0"

        if chart_series.find("Type") is None:
            chart_type = etree.SubElement(chart_series, "Type")
            chart_type.text = "Column"

        chart_areas = chart.find("ChartAreas")
        if chart_areas is None:
            chart_areas = etree.SubElement(chart, "ChartAreas")
        chart_area = chart_areas.find("ChartArea")
        if chart_area is None:
            chart_area = etree.SubElement(chart_areas, "ChartArea")
            chart_area.set("Name", "Default")
        elif not chart_area.get("Name"):
            chart_area.set("Name", "Default")

        area_name = chart_series.find("ChartAreaName")
        if area_name is None:
            area_name = etree.SubElement(chart_series, "ChartAreaName")
            area_name.text = "Default"

    def _normalize_chart_hierarchy(self, chart, hierarchy_tag: str) -> None:
        hierarchy = chart.find(hierarchy_tag)
        if hierarchy is None:
            return

        # Rebuild hierarchy to the schema-safe shape:
        # <ChartCategoryHierarchy|ChartSeriesHierarchy><ChartMembers>...</ChartMembers></...>
        collected_members = [copy.deepcopy(member) for member in hierarchy.findall(".//ChartMembers/ChartMember")]

        for child in list(hierarchy):
            hierarchy.remove(child)

        members_container = etree.SubElement(hierarchy, "ChartMembers")
        for member in collected_members:
            members_container.append(member)

    def _build_chart(self, visual, dataset, rect):
        chart = etree.Element("Chart")
        chart.set("Name", self._safe_name(visual.id, "chart"))
        self._apply_rect(chart, rect)

        ds_name = etree.SubElement(chart, "DataSetName")
        ds_name.text = self._dataset_name(dataset)

        self._ensure_chart_minimum(chart, visual)

        return chart

    def _build_tablix(self, visual, dataset, rect):
        tablix = etree.Element("Tablix")
        tablix.set("Name", self._safe_name(visual.id, "tablix"))
        self._apply_rect(tablix, rect)

        ds_name = etree.SubElement(tablix, "DataSetName")
        ds_name.text = self._dataset_name(dataset)

        body = etree.SubElement(tablix, "TablixBody")
        cols_el = etree.SubElement(body, "TablixColumns")
        rows_el = etree.SubElement(body, "TablixRows")

        visible_fields = dataset.fields[:10]
        width = rect.width / max(len(visible_fields), 1)

        for _field in visible_fields:
            col_el = etree.SubElement(cols_el, "TablixColumn")
            width_el = etree.SubElement(col_el, "Width")
            width_el.text = f"{width:.4f}in"

        header_row = etree.SubElement(rows_el, "TablixRow")
        h_height = etree.SubElement(header_row, "Height")
        h_height.text = "0.25in"
        h_cells = etree.SubElement(header_row, "TablixCells")

        for field in visible_fields:
            cell = etree.SubElement(h_cells, "TablixCell")
            contents = etree.SubElement(cell, "CellContents")
            textbox = etree.SubElement(contents, "Textbox")
            textbox.set("Name", self._safe_name(f"Header_{field.name}", "Header_Field"))
            paragraphs = etree.SubElement(textbox, "Paragraphs")
            paragraph = etree.SubElement(paragraphs, "Paragraph")
            text_runs = etree.SubElement(paragraph, "TextRuns")
            run = etree.SubElement(text_runs, "TextRun")
            value = etree.SubElement(run, "Value")
            value.text = field.name

        data_row = etree.SubElement(rows_el, "TablixRow")
        d_height = etree.SubElement(data_row, "Height")
        d_height.text = "0.25in"
        d_cells = etree.SubElement(data_row, "TablixCells")

        for field in visible_fields:
            cell = etree.SubElement(d_cells, "TablixCell")
            contents = etree.SubElement(cell, "CellContents")
            textbox = etree.SubElement(contents, "Textbox")
            textbox.set("Name", self._safe_name(f"Data_{field.name}", "Data_Field"))
            paragraphs = etree.SubElement(textbox, "Paragraphs")
            paragraph = etree.SubElement(paragraphs, "Paragraph")
            text_runs = etree.SubElement(paragraph, "TextRuns")
            run = etree.SubElement(text_runs, "TextRun")
            value = etree.SubElement(run, "Value")
            value.text = f"=Fields!{field.name}.Value"

        return tablix

    def _build_kpi_textbox(self, visual, dataset, rect):
        textbox = etree.Element("Textbox")
        textbox.set("Name", self._safe_name(visual.id, "textbox"))
        self._apply_rect(textbox, rect)

        paragraphs = etree.SubElement(textbox, "Paragraphs")
        paragraph = etree.SubElement(paragraphs, "Paragraph")
        text_runs = etree.SubElement(paragraph, "TextRuns")
        run = etree.SubElement(text_runs, "TextRun")
        value = etree.SubElement(run, "Value")

        if visual.data_binding.measures:
            measure = visual.data_binding.measures[0]
            value.text = f"=Sum(Fields!{measure.name}.Value)"
        else:
            value.text = "=0"

        style = etree.SubElement(textbox, "Style")
        font_size = etree.SubElement(style, "FontSize")
        font_size.text = "20pt"
        font_weight = etree.SubElement(style, "FontWeight")
        font_weight.text = "Bold"
        text_align = etree.SubElement(style, "TextAlign")
        text_align.text = "Center"

        return textbox
