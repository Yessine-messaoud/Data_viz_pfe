from __future__ import annotations

import copy
import re

from lxml import etree

from viz_agent.chart_type_registry import series_from_override, series_rule_for


CHART_RDL_TYPES = {
    "chart",
    "columnchart",
    "linechart",
    "piechart",
    "treemap",
    "scatterchart",
}


class RDLVisualMapper:
    def __init__(self, llm_client=None, use_llm: bool = True, semantic_model=None):
        _ = llm_client, use_llm
        self.semantic_model = semantic_model
        self.measure_alias_map = self._build_measure_alias_map(semantic_model)

    def _normalize_identifier(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).lower()

    def _extract_column_from_expression(self, expression: str) -> str | None:
        text = str(expression or "").strip()
        if not text:
            return None

        # Handles common generated patterns like SUM(('Extract','Extract').TotalSales)
        match = re.search(r"\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", text)
        if match:
            return match.group(1)
        return None

    def _build_measure_alias_map(self, semantic_model) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        if semantic_model is None:
            return alias_map

        for entity in getattr(semantic_model, "entities", []) or []:
            for col in getattr(entity, "columns", []) or []:
                if getattr(col, "role", "") != "measure":
                    continue
                col_name = str(getattr(col, "name", "") or "").strip()
                col_label = str(getattr(col, "label", "") or "").strip()
                if col_name:
                    alias_map[col_name] = col_name
                    alias_map[self._normalize_identifier(col_name)] = col_name
                if col_label:
                    alias_map[col_label] = col_name
                    alias_map[self._normalize_identifier(col_label)] = col_name

        for measure in getattr(semantic_model, "measures", []) or []:
            measure_name = str(getattr(measure, "name", "") or "").strip()
            source_name = str(getattr(measure, "tableau_expression", "") or "").strip()
            inferred = self._extract_column_from_expression(str(getattr(measure, "expression", "") or ""))

            technical_name = source_name if source_name and source_name != "calculated" else inferred
            if not technical_name:
                continue

            alias_map[technical_name] = technical_name
            alias_map[self._normalize_identifier(technical_name)] = technical_name

            if measure_name:
                alias_map[measure_name] = technical_name
                alias_map[self._normalize_identifier(measure_name)] = technical_name

        return alias_map

    def _resolve_field_name(self, candidate: str, dataset) -> str | None:
        field_names = [str(getattr(field, "name", "") or "") for field in getattr(dataset, "fields", [])]
        if not field_names:
            return None

        direct = str(candidate or "").strip()

        # Prefer descriptive aliases when both legacy short names and business-friendly names exist.
        if direct == "TaxAmt" and "TaxAmount" in field_names:
            return "TaxAmount"

        if direct and direct in field_names:
            return direct

        mapped = self.measure_alias_map.get(direct) or self.measure_alias_map.get(self._normalize_identifier(direct))
        if mapped and mapped in field_names:
            return mapped

        normalized_fields = {self._normalize_identifier(name): name for name in field_names}
        candidate_norm = self._normalize_identifier(direct)
        if candidate_norm and candidate_norm in normalized_fields:
            return normalized_fields[candidate_norm]

        if mapped:
            mapped_norm = self._normalize_identifier(mapped)
            if mapped_norm in normalized_fields:
                return normalized_fields[mapped_norm]

        return None

    def _resolve_y_field_name(self, visual, dataset) -> str | None:
        axis_y = visual.data_binding.axes.get("y") if hasattr(visual.data_binding, "axes") else None
        candidates: list[str] = []
        # Prefer explicit measures before generic axis bindings to avoid SUM over text dimensions.
        for measure_ref in getattr(visual.data_binding, "measures", []) or []:
            if hasattr(measure_ref, "name"):
                candidates.append(str(measure_ref.name))

        if axis_y is not None:
            if hasattr(axis_y, "column"):
                candidates.append(str(axis_y.column))
            if hasattr(axis_y, "name"):
                candidates.append(str(axis_y.name))

        candidates.append("TotalSales")

        for candidate in candidates:
            resolved = self._resolve_field_name(candidate, dataset)
            if resolved and self._is_valid_y_field(resolved, dataset):
                return resolved

        # Fallback: choose the first field that looks like a measure.
        for field in getattr(dataset, "fields", []) or []:
            field_name = str(getattr(field, "name", "") or "").strip()
            if field_name and self._is_valid_y_field(field_name, dataset):
                return field_name

        return None

    def _is_valid_y_field(self, field_name: str, dataset) -> bool:
        normalized = self._normalize_identifier(field_name)
        for field in getattr(dataset, "fields", []) or []:
            candidate = str(getattr(field, "name", "") or "").strip()
            if self._normalize_identifier(candidate) != normalized:
                continue
            rdl_type = str(getattr(field, "rdl_type", "") or "").strip().lower()
            if rdl_type in {"integer", "int16", "int32", "int64", "long", "float", "double", "decimal", "currency", "single"}:
                return True
            break

        lowered = str(field_name or "").strip().lower()
        if any(token in lowered for token in ("country", "region", "category", "model", "type", "channel", "priority", "date")):
            return False
        if any(token in lowered for token in ("amount", "tax", "price", "cost", "profit", "quantity", "qty", "sold", "count", "revenue", "total")):
            return True
        return False

    def _resolve_x_field_name(self, visual, dataset) -> str | None:
        axis_x = visual.data_binding.axes.get("x") if hasattr(visual.data_binding, "axes") else None
        candidates: list[str] = []
        if axis_x is not None:
            if hasattr(axis_x, "column"):
                candidates.append(str(axis_x.column))
            if hasattr(axis_x, "name"):
                candidates.append(str(axis_x.name))

        for preferred in ("Country", "SalesTerritoryCountry", "Region", "Category", "ModelName"):
            candidates.append(preferred)

        for candidate in candidates:
            resolved = self._resolve_field_name(candidate, dataset)
            if resolved:
                return resolved

        # Final fallback: first string-like field if available.
        for field in getattr(dataset, "fields", []) or []:
            f_name = str(getattr(field, "name", "") or "").strip()
            f_type = str(getattr(field, "rdl_type", "") or "").strip().lower()
            if f_name and f_type == "string":
                return f_name
        for field in getattr(dataset, "fields", []) or []:
            f_name = str(getattr(field, "name", "") or "").strip()
            if f_name:
                return f_name
        return None

    def _resolve_color_field_name(self, visual, dataset) -> str | None:
        axis_color = visual.data_binding.axes.get("color") if hasattr(visual.data_binding, "axes") else None
        candidates: list[str] = []
        if axis_color is not None:
            if hasattr(axis_color, "column"):
                candidates.append(str(axis_color.column))
            if hasattr(axis_color, "name"):
                candidates.append(str(axis_color.name))

        for candidate in candidates:
            resolved = self._resolve_field_name(candidate, dataset)
            if resolved:
                return resolved
        return None

    def _safe_name(self, value: str, fallback: str) -> str:
        # RDL Name attributes must be XML-friendly and stable.
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "")).strip("_")
        if not cleaned:
            cleaned = fallback
        if not re.match(r"^[A-Za-z_]", cleaned):
            cleaned = f"_{cleaned}"
        return cleaned[:120]

    def _caption_from_field_name(self, field_name: str) -> str:
        value = str(field_name or "").strip()
        if not value:
            return ""
        return re.sub(r"(?<!^)([A-Z])", r" \1", value).strip()

    def _dataset_name(self, dataset) -> str:
        return str(getattr(dataset, "rdl_name", getattr(dataset, "name", "DataSet1")))

    def _resolve_rdl_visual_type(self, visual) -> str:
        logical = str(getattr(visual, "type", "") or "").strip().lower()
        rdl_type = str(getattr(visual, "rdl_type", "") or "").strip().lower()
        if rdl_type:
            # Backward compatibility: many tests/legacy specs set `type` only.
            if rdl_type == "tablix" and logical in {"chart", "map", "textbox"}:
                return logical
            if rdl_type in CHART_RDL_TYPES:
                return "chart"
            return rdl_type
        if logical in {"bar", "line", "scatter", "pie", "treemap", "chart"}:
            return "chart"
        if logical in {"table", "tablix", "gantt"}:
            return "tablix"
        if logical in {"kpi", "textbox"}:
            return "textbox"
        if logical == "map":
            return "map"
        return "tablix"

    def _resolve_chart_series_type(self, visual) -> tuple[str, str | None]:
        # Prefer the explicit rdl_type produced by Phase 3/4 over generic defaults.
        declared_rdl_type = str(getattr(visual, "rdl_type", "") or "").strip().lower()
        by_rdl_type = {
            "columnchart": ("Column", None),
            "linechart": ("Line", None),
            "piechart": ("Shape", "Pie"),
            "scatterchart": ("Scatter", None),
            # Treemap remains mapped to a stable column fallback renderer for SSRS compatibility.
            "treemap": ("Column", None),
        }
        if declared_rdl_type in by_rdl_type:
            return by_rdl_type[declared_rdl_type]

        override = ""
        if hasattr(visual, "data_binding"):
            override = str(getattr(visual.data_binding, "visual_type_override", "") or "").strip().lower()

        override_rule = series_from_override(override)
        if override_rule is not None:
            return override_rule

        logical = str(getattr(visual, "type", "") or "").strip().lower()
        rule = series_rule_for(logical)
        if rule is not None:
            return (rule.series_type, rule.series_subtype)
        return ("Column", None)

    def map_visual(self, visual, dataset, rect):
        # Charts are generated with deterministic XML because free-form LLM chart XML
        # frequently breaks strict SSRS schema constraints.
        rdl_type = self._resolve_rdl_visual_type(visual)
        if rdl_type == "chart":
            return self._build_chart(visual, dataset, rect)

        if rdl_type == "tablix":
            return self._build_tablix(visual, dataset, rect)
        if rdl_type == "textbox":
            return self._build_kpi_textbox(visual, dataset, rect)
        return self._build_tablix(visual, dataset, rect)

    def _apply_rect(self, element: etree._Element, rect) -> None:
        for attr, value in rect.to_rdl().items():
            sub = etree.SubElement(element, attr)
            sub.text = value

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
            self._ensure_chart_minimum(element, visual, dataset)
        if expected_tag == "Tablix":
            self._ensure_tablix_minimum(element)

    def _ensure_chart_minimum(self, chart, visual, dataset) -> None:
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
            x_field_name = self._resolve_x_field_name(visual, dataset)
            if x_field_name:
                category_label.text = f"=Fields!{x_field_name}.Value"
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

            group = member.find("Group")
            if group is None:
                x_field_name = self._resolve_x_field_name(visual, dataset)
                if x_field_name:
                    group_expr = f"=Fields!{x_field_name}.Value"
                    group_name = self._safe_name(f"grp_{x_field_name}", "grp_Category")
                else:
                    group_expr = "=\"Category\""
                    group_name = "grp_Category"

                group = etree.SubElement(member, "Group")
                group.set("Name", group_name)
                expressions = etree.SubElement(group, "GroupExpressions")
                expression = etree.SubElement(expressions, "GroupExpression")
                expression.text = group_expr

        x_field_name = self._resolve_x_field_name(visual, dataset)
        y_field_name = self._resolve_y_field_name(visual, dataset)
        color_field_name = self._resolve_color_field_name(visual, dataset)
        series_caption = self._caption_from_field_name(y_field_name or "")
        if not series_caption:
            series_caption = str(getattr(visual, "title", "") or "Series").strip() or "Series"
        series_caption = series_caption.replace('"', "'")

        for member in chart.findall(".//ChartSeriesHierarchy//ChartMember"):
            if color_field_name:
                group = member.find("Group")
                if group is None:
                    group = etree.SubElement(member, "Group")
                group.set("Name", self._safe_name(f"grp_series_{color_field_name}", "grp_series"))
                expressions = group.find("GroupExpressions")
                if expressions is None:
                    expressions = etree.SubElement(group, "GroupExpressions")
                expression = expressions.find("GroupExpression")
                if expression is None:
                    expression = etree.SubElement(expressions, "GroupExpression")
                expression.text = f"=Fields!{color_field_name}.Value"

            label = member.find("Label")
            if label is None:
                label = etree.SubElement(member, "Label")
            current = str(label.text or "").strip().strip('"').strip("=")
            if (
                label.text is None
                or not str(label.text).strip()
                or current.lower() in {"series", "series1", "series2"}
            ):
                if color_field_name:
                    label.text = f"=Fields!{color_field_name}.Value"
                else:
                    label.text = f"=\"{series_caption}\""

        chart_data = chart.find("ChartData")
        if chart_data is None:
            chart_data = etree.SubElement(chart, "ChartData")
        series_collection = chart_data.find("ChartSeriesCollection")
        if series_collection is None:
            series_collection = etree.SubElement(chart_data, "ChartSeriesCollection")
        chart_series = series_collection.find("ChartSeries")
        if chart_series is None:
            chart_series = etree.SubElement(series_collection, "ChartSeries")
            chart_series.set("Name", self._safe_name(series_caption, self._safe_name(f"series_{visual.id}", "series_1")))
        else:
            existing_name = str(chart_series.get("Name", "") or "").strip().lower()
            if not existing_name or existing_name == "series" or existing_name.startswith("series_"):
                chart_series.set("Name", self._safe_name(series_caption, self._safe_name(f"series_{visual.id}", "series_1")))

        points = chart_series.find("ChartDataPoints")
        if points is None:
            points = etree.SubElement(chart_series, "ChartDataPoints")
        point = points.find("ChartDataPoint")
        if point is None:
            point = etree.SubElement(points, "ChartDataPoint")
        values = point.find("ChartDataPointValues")
        if values is None:
            values = etree.SubElement(point, "ChartDataPointValues")
        y_val = values.find("Y")
        if y_val is None:
            y_val = etree.SubElement(values, "Y")

        y_field_name = self._resolve_y_field_name(visual, dataset)
        if y_field_name:
            y_val.text = f"=Sum(Fields!{y_field_name}.Value)"
        elif y_val.text is None or not str(y_val.text).strip() or str(y_val.text).strip() == "=0":
            y_val.text = "=Sum(Fields!TotalSales.Value)"

        series_type, series_subtype = self._resolve_chart_series_type(visual)
        chart_type = chart_series.find("Type")
        if chart_type is None:
            chart_type = etree.SubElement(chart_series, "Type")
        # Enforce subtype from abstract spec/logical type to avoid ambiguous defaults.
        chart_type.text = series_type

        subtype_node = chart_series.find("Subtype")
        if series_subtype:
            if subtype_node is None:
                subtype_node = etree.SubElement(chart_series, "Subtype")
            subtype_node.text = series_subtype
        elif subtype_node is not None:
            chart_series.remove(subtype_node)

        # RDL 2016 expects ChartTitles/ChartTitle (not ChartTitle directly under Chart).
        legacy_chart_title = chart.find("ChartTitle")
        chart_titles = chart.find("ChartTitles")
        if chart_titles is None:
            chart_titles = etree.SubElement(chart, "ChartTitles")
        chart_title = chart_titles.find("ChartTitle")
        if chart_title is None:
            chart_title = etree.SubElement(chart_titles, "ChartTitle")
        if not chart_title.get("Name"):
            chart_title.set("Name", "DefaultTitle")
        if legacy_chart_title is not None:
            legacy_caption = legacy_chart_title.findtext("Caption")
            if legacy_caption and not chart_title.findtext("Caption"):
                migrated_caption = etree.SubElement(chart_title, "Caption")
                migrated_caption.text = legacy_caption
            chart.remove(legacy_chart_title)

        caption = chart_title.find("Caption")
        if caption is None:
            caption = etree.SubElement(chart_title, "Caption")
        if caption.text is None or not str(caption.text).strip():
            caption.text = str(getattr(visual, "title", "") or getattr(visual, "source_worksheet", "") or "Chart")

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

        category_axes = chart_area.find("ChartCategoryAxes")
        if category_axes is None:
            category_axes = etree.SubElement(chart_area, "ChartCategoryAxes")
        category_axis = category_axes.find("ChartAxis")
        if category_axis is None:
            legacy_axis = category_axes.find("ChartCategoryAxis")
            if legacy_axis is not None:
                category_axis = etree.SubElement(category_axes, "ChartAxis")
                for child in list(legacy_axis):
                    category_axis.append(copy.deepcopy(child))
                category_axes.remove(legacy_axis)
            else:
                category_axis = etree.SubElement(category_axes, "ChartAxis")
        if not category_axis.get("Name"):
            category_axis.set("Name", "CategoryAxis1")
        cat_title = category_axis.find("ChartAxisTitle")
        if cat_title is None:
            legacy_title = category_axis.find("AxisTitle")
            if legacy_title is not None:
                cat_title = etree.SubElement(category_axis, "ChartAxisTitle")
                for child in list(legacy_title):
                    cat_title.append(copy.deepcopy(child))
                category_axis.remove(legacy_title)
            else:
                cat_title = etree.SubElement(category_axis, "ChartAxisTitle")
        cat_caption = cat_title.find("Caption")
        if cat_caption is None:
            cat_caption = etree.SubElement(cat_title, "Caption")
        if cat_caption.text is None or not str(cat_caption.text).strip():
            cat_caption.text = self._caption_from_field_name(x_field_name or "Category")

        value_axes = chart_area.find("ChartValueAxes")
        if value_axes is None:
            value_axes = etree.SubElement(chart_area, "ChartValueAxes")
        value_axis = value_axes.find("ChartAxis")
        if value_axis is None:
            legacy_axis = value_axes.find("ChartValueAxis")
            if legacy_axis is not None:
                value_axis = etree.SubElement(value_axes, "ChartAxis")
                for child in list(legacy_axis):
                    value_axis.append(copy.deepcopy(child))
                value_axes.remove(legacy_axis)
            else:
                value_axis = etree.SubElement(value_axes, "ChartAxis")
        if not value_axis.get("Name"):
            value_axis.set("Name", "ValueAxis1")
        val_title = value_axis.find("ChartAxisTitle")
        if val_title is None:
            legacy_title = value_axis.find("AxisTitle")
            if legacy_title is not None:
                val_title = etree.SubElement(value_axis, "ChartAxisTitle")
                for child in list(legacy_title):
                    val_title.append(copy.deepcopy(child))
                value_axis.remove(legacy_title)
            else:
                val_title = etree.SubElement(value_axis, "ChartAxisTitle")
        val_caption = val_title.find("Caption")
        if val_caption is None:
            val_caption = etree.SubElement(val_title, "Caption")
        if val_caption.text is None or not str(val_caption.text).strip():
            val_caption.text = self._caption_from_field_name(y_field_name or "Value")

        legends = chart.find("ChartLegends")
        if legends is None:
            legends = etree.SubElement(chart, "ChartLegends")
        legend = legends.find("ChartLegend")
        if legend is None:
            legend = etree.SubElement(legends, "ChartLegend")
            legend.set("Name", "DefaultLegend")
        elif not legend.get("Name"):
            legend.set("Name", "DefaultLegend")

        legend_name = chart_series.find("LegendName")
        if legend_name is None:
            legend_name = etree.SubElement(chart_series, "LegendName")
        if legend_name.text is None or not str(legend_name.text).strip():
            legend_name.text = "DefaultLegend"

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

        self._ensure_chart_minimum(chart, visual, dataset)

        return chart

    def _build_tablix(self, visual, dataset, rect):
        tablix = etree.Element("Tablix")
        tablix_name = self._safe_name(visual.id, "tablix")
        tablix.set("Name", tablix_name)
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
            textbox.set("Name", self._safe_name(f"{tablix_name}_Header_{field.name}", "Header_Field"))
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
            textbox.set("Name", self._safe_name(f"{tablix_name}_Data_{field.name}", "Data_Field"))
            paragraphs = etree.SubElement(textbox, "Paragraphs")
            paragraph = etree.SubElement(paragraphs, "Paragraph")
            text_runs = etree.SubElement(paragraph, "TextRuns")
            run = etree.SubElement(text_runs, "TextRun")
            value = etree.SubElement(run, "Value")
            value.text = f"=Fields!{field.name}.Value"

        self._ensure_tablix_minimum(tablix)
        return tablix

    def _ensure_tablix_minimum(self, tablix: etree._Element) -> None:
        body = tablix.find("TablixBody")
        if body is None:
            return

        cols_container = body.find("TablixColumns")
        if cols_container is None:
            cols_container = etree.SubElement(body, "TablixColumns")
        rows_container = body.find("TablixRows")
        if rows_container is None:
            rows_container = etree.SubElement(body, "TablixRows")

        cols = cols_container.findall("TablixColumn")
        if not cols:
            col = etree.SubElement(cols_container, "TablixColumn")
            width = etree.SubElement(col, "Width")
            width.text = "1in"
            cols = cols_container.findall("TablixColumn")
        else:
            for col in cols:
                if col.find("Width") is None:
                    width = etree.SubElement(col, "Width")
                    width.text = "1in"

        rows = rows_container.findall("TablixRow")
        if not rows:
            default_row = etree.SubElement(rows_container, "TablixRow")
            height = etree.SubElement(default_row, "Height")
            height.text = "0.25in"
            rows = rows_container.findall("TablixRow")

        col_count = max(1, len(cols))
        row_count = max(1, len(rows))

        tablix_name = str(tablix.get("Name", "Tablix"))
        for row_idx, row in enumerate(rows):
            if row.find("Height") is None:
                height = etree.SubElement(row, "Height")
                height.text = "0.25in"

            cells_container = row.find("TablixCells")
            if cells_container is None:
                cells_container = etree.SubElement(row, "TablixCells")

            cells = cells_container.findall("TablixCell")
            if len(cells) != col_count:
                for child in list(cells_container):
                    cells_container.remove(child)
                for col_idx in range(col_count):
                    cell = etree.SubElement(cells_container, "TablixCell")
                    contents = etree.SubElement(cell, "CellContents")
                    textbox = etree.SubElement(contents, "Textbox")
                    textbox.set("Name", self._safe_name(f"{tablix_name}_Auto_{row_idx}_{col_idx}", "AutoCell"))
                    paragraphs = etree.SubElement(textbox, "Paragraphs")
                    paragraph = etree.SubElement(paragraphs, "Paragraph")
                    text_runs = etree.SubElement(paragraph, "TextRuns")
                    run = etree.SubElement(text_runs, "TextRun")
                    value = etree.SubElement(run, "Value")
                    value.text = ""
            else:
                for col_idx, cell in enumerate(cells):
                    contents = cell.find("CellContents")
                    if contents is None:
                        contents = etree.SubElement(cell, "CellContents")
                    if contents.find("Textbox") is None:
                        textbox = etree.SubElement(contents, "Textbox")
                        textbox.set("Name", self._safe_name(f"{tablix_name}_Auto_{row_idx}_{col_idx}", "AutoCell"))
                        paragraphs = etree.SubElement(textbox, "Paragraphs")
                        paragraph = etree.SubElement(paragraphs, "Paragraph")
                        text_runs = etree.SubElement(paragraph, "TextRuns")
                        run = etree.SubElement(text_runs, "TextRun")
                        value = etree.SubElement(run, "Value")
                        value.text = ""

        col_hierarchy = tablix.find("TablixColumnHierarchy")
        if col_hierarchy is None:
            col_hierarchy = etree.SubElement(tablix, "TablixColumnHierarchy")
        col_members = col_hierarchy.find("TablixMembers")
        if col_members is None:
            col_members = etree.SubElement(col_hierarchy, "TablixMembers")
        if len(col_members.findall("TablixMember")) != col_count:
            for child in list(col_members):
                col_members.remove(child)
            for _ in range(col_count):
                etree.SubElement(col_members, "TablixMember")

        row_hierarchy = tablix.find("TablixRowHierarchy")
        if row_hierarchy is None:
            row_hierarchy = etree.SubElement(tablix, "TablixRowHierarchy")
        row_members = row_hierarchy.find("TablixMembers")
        if row_members is None:
            row_members = etree.SubElement(row_hierarchy, "TablixMembers")
        if len(row_members.findall("TablixMember")) != row_count:
            for child in list(row_members):
                row_members.remove(child)
            for _ in range(row_count):
                etree.SubElement(row_members, "TablixMember")

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
            resolved_measure = self._resolve_field_name(str(measure.name), dataset) or str(measure.name)
            value.text = f"=Sum(Fields!{resolved_measure}.Value)"
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
