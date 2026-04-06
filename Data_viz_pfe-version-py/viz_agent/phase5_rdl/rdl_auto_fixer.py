from __future__ import annotations

import re

from lxml import etree

from viz_agent.models.validation import Issue


class RDLAutoFixer:
    NON_DESTRUCTIVE_CODES = {
        "X002",
        "X006",
        "S007",
        "S005",
        "S005c",
        "S005d",
        "S005e",
        "S005f",
        "S003f",
        "S008c",
        "S008d",
        "S008e",
        "S009",
    }

    def __init__(self) -> None:
        self.fix_log: list[str] = []

    def fix_all(self, rdl_content: str, issues: list[Issue]) -> tuple[str, list[str]]:
        self.fix_log = []
        current = rdl_content

        for issue in issues:
            if issue.severity != "error" and issue.code != "X006":
                continue
            if issue.code not in self.NON_DESTRUCTIVE_CODES:
                continue
            fixer = self._get_fixer(issue.code)
            if fixer is None:
                continue
            updated = fixer(current, issue)
            if updated != current:
                current = updated
        return current, self.fix_log

    def _get_fixer(self, code: str):
        return {
            "X002": self._fix_namespace,
            "X005": self._fix_control_chars,
            "X006": self._fix_unescaped_attrs,
            "S007": self._fix_dimension,
            "S005": self._fix_tablix_hierarchies,
            "S005d": self._fix_tablix_hierarchies,
            "S005e": self._fix_tablix_hierarchies,
            "S005f": self._fix_tablix_rows_cells,
            "S005c": self._fix_chart_member_labels,
            "S003f": self._fix_duplicate_dataset_fields,
            "S008c": self._fix_duplicate_report_parameters,
            "S009": self._fix_duplicate_report_item_names,
            "S008d": self._fix_invalid_report_parameter_names,
            "S008e": self._fix_mismatched_parameter_layout,
        }.get(code)

    def _fix_namespace(self, rdl: str, issue: Issue) -> str:
        target = issue.auto_fix or "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
        replaced = re.sub(
            r'xmlns="http://schemas\.microsoft\.com/sqlserver/reporting/\d+/\d+/reportdefinition"',
            f'xmlns="{target}"',
            rdl,
            count=1,
        )
        if replaced == rdl and "<Report" in rdl and "xmlns=" not in rdl.split(">", 1)[0]:
            replaced = rdl.replace("<Report", f'<Report xmlns="{target}"', 1)

        if replaced != rdl:
            self.fix_log.append("[X002] normalized RDL namespace")
        return replaced

    def _fix_control_chars(self, rdl: str, issue: Issue) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", rdl)
        if cleaned != rdl:
            self.fix_log.append("[X005] removed forbidden control characters")
        return cleaned

    def _fix_unescaped_attrs(self, rdl: str, issue: Issue) -> str:
        def _escape_attr(match: re.Match[str]) -> str:
            attr = match.group(0)
            return re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;|#)", "&amp;", attr)

        updated = re.sub(r'="[^"]*"', _escape_attr, rdl)
        if updated != rdl:
            self.fix_log.append("[X006] escaped '&' in XML attributes")
        return updated

    def _fix_dimension(self, rdl: str, issue: Issue) -> str:
        tags = [
            "Width",
            "Height",
            "Top",
            "Left",
            "MarginTop",
            "MarginBottom",
            "MarginLeft",
            "MarginRight",
            "PageWidth",
            "PageHeight",
        ]
        current = rdl
        for tag in tags:
            current = re.sub(
                rf"<{tag}>(-?\\d+(?:\\.\\d+)?)</{tag}>",
                rf"<{tag}>\\1in</{tag}>",
                current,
            )
        if current != rdl:
            self.fix_log.append("[S007] added default 'in' unit to numeric dimensions")
        return current

    def _fix_chart_member_labels(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            for chart_member in root.xpath(".//*[local-name()='ChartMember']"):
                label = self._find_child_local(chart_member, "Label")
                if label is None:
                    label = self._append_same_ns(chart_member, "Label")
                    changed = True
                if label.text is None or not str(label.text).strip():
                    label.text = '="Series"'
                    changed = True
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S005c] added missing ChartMember labels")

    def _fix_tablix_hierarchies(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            for tablix in root.xpath(".//*[local-name()='Tablix']"):
                body = self._find_child_local(tablix, "TablixBody")
                if body is None:
                    continue

                col_count = self._count_children_path(body, ["TablixColumns", "TablixColumn"])
                row_count = self._count_children_path(body, ["TablixRows", "TablixRow"])
                col_count = max(1, col_count)
                row_count = max(1, row_count)

                if self._ensure_hierarchy_members(tablix, "TablixColumnHierarchy", col_count):
                    changed = True
                if self._ensure_hierarchy_members(tablix, "TablixRowHierarchy", row_count):
                    changed = True
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S005] normalized Tablix hierarchies")

    def _fix_tablix_rows_cells(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            for tablix in root.xpath(".//*[local-name()='Tablix']"):
                body = self._find_child_local(tablix, "TablixBody")
                if body is None:
                    continue
                cols = self._find_child_local(body, "TablixColumns")
                rows = self._find_child_local(body, "TablixRows")
                if cols is None or rows is None:
                    continue

                col_nodes = [c for c in cols if isinstance(c.tag, str) and etree.QName(c.tag).localname == "TablixColumn"]
                col_count = max(1, len(col_nodes))
                tablix_name = str(tablix.get("Name", "Tablix"))

                row_nodes = [r for r in rows if isinstance(r.tag, str) and etree.QName(r.tag).localname == "TablixRow"]
                for row_idx, row in enumerate(row_nodes):
                    cells = self._find_child_local(row, "TablixCells")
                    if cells is None:
                        cells = self._append_same_ns(row, "TablixCells")
                        changed = True

                    cell_nodes = [c for c in cells if isinstance(c.tag, str) and etree.QName(c.tag).localname == "TablixCell"]
                    if len(cell_nodes) != col_count:
                        for child in list(cells):
                            cells.remove(child)
                        for col_idx in range(col_count):
                            cell = self._append_same_ns(cells, "TablixCell")
                            contents = self._append_same_ns(cell, "CellContents")
                            textbox = self._append_same_ns(contents, "Textbox")
                            textbox.set("Name", f"{tablix_name}_Auto_{row_idx}_{col_idx}")
                            paragraphs = self._append_same_ns(textbox, "Paragraphs")
                            paragraph = self._append_same_ns(paragraphs, "Paragraph")
                            text_runs = self._append_same_ns(paragraph, "TextRuns")
                            run = self._append_same_ns(text_runs, "TextRun")
                            value = self._append_same_ns(run, "Value")
                            value.text = ""
                        changed = True
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S005f] normalized TablixRow/TablixCells structure")

    def _ensure_hierarchy_members(self, parent: etree._Element, hierarchy_tag: str, count: int) -> bool:
        changed = False
        hierarchy = self._find_child_local(parent, hierarchy_tag)
        if hierarchy is None:
            hierarchy = self._append_same_ns(parent, hierarchy_tag)
            changed = True

        members = self._find_child_local(hierarchy, "TablixMembers")
        if members is None:
            members = self._append_same_ns(hierarchy, "TablixMembers")
            changed = True

        existing = [child for child in list(members) if etree.QName(child.tag).localname == "TablixMember"]
        if len(existing) != count:
            for child in list(members):
                members.remove(child)
            for _ in range(count):
                self._append_same_ns(members, "TablixMember")
            changed = True
        return changed

    def _apply_xml_fix(self, rdl: str, mutator, log_message: str) -> str:
        try:
            parser = etree.XMLParser(recover=False, remove_blank_text=False)
            root = etree.fromstring(rdl.encode("utf-8"), parser=parser)
        except Exception:
            return rdl

        changed = mutator(root)
        if not changed:
            return rdl

        has_declaration = rdl.lstrip().startswith("<?xml")
        updated = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=has_declaration,
            encoding="UTF-8",
        ).decode("utf-8")
        self.fix_log.append(log_message)
        return updated

    @staticmethod
    def _find_child_local(parent: etree._Element, local_name: str) -> etree._Element | None:
        for child in parent:
            if isinstance(child.tag, str) and etree.QName(child.tag).localname == local_name:
                return child
        return None

    @staticmethod
    def _append_same_ns(parent: etree._Element, local_name: str) -> etree._Element:
        namespace = etree.QName(parent.tag).namespace
        if namespace:
            return etree.SubElement(parent, f"{{{namespace}}}{local_name}")
        return etree.SubElement(parent, local_name)

    def _count_children_path(self, parent: etree._Element, path: list[str]) -> int:
        node = parent
        for step in path[:-1]:
            next_node = self._find_child_local(node, step)
            if next_node is None:
                return 0
            node = next_node
        target_name = path[-1]
        return sum(
            1
            for child in node
            if isinstance(child.tag, str) and etree.QName(child.tag).localname == target_name
        )

    def _fix_duplicate_dataset_fields(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            for dataset in root.xpath(".//*[local-name()='DataSet']"):
                fields = self._find_child_local(dataset, "Fields")
                if fields is None:
                    continue
                seen: set[str] = set()
                for field in list(fields):
                    if not isinstance(field.tag, str) or etree.QName(field.tag).localname != "Field":
                        continue
                    name = str(field.get("Name", "")).strip().lower()
                    if not name:
                        continue
                    if name in seen:
                        fields.remove(field)
                        changed = True
                        continue
                    seen.add(name)
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S003f] removed duplicate DataSet Field names")

    def _fix_duplicate_report_parameters(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            for params in root.xpath(".//*[local-name()='ReportParameters']"):
                seen: set[str] = set()
                for param in list(params):
                    if not isinstance(param.tag, str) or etree.QName(param.tag).localname != "ReportParameter":
                        continue
                    name = str(param.get("Name", "")).strip().lower()
                    if not name:
                        continue
                    if name in seen:
                        params.remove(param)
                        changed = True
                        continue
                    seen.add(name)
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S008c] removed duplicate ReportParameter names")

    def _fix_duplicate_report_item_names(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            used: set[str] = set()
            suffix_by_base: dict[str, int] = {}

            for item in root.xpath(".//*[local-name()='ReportItems']/*[@Name]"):
                if not isinstance(item.tag, str):
                    continue
                name = str(item.get("Name", "")).strip()
                if not name:
                    continue
                lower = name.lower()
                if lower not in used:
                    used.add(lower)
                    continue

                base = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_") or "ReportItem"
                next_suffix = suffix_by_base.get(base, 2)
                candidate = f"{base}_{next_suffix}"
                while candidate.lower() in used:
                    next_suffix += 1
                    candidate = f"{base}_{next_suffix}"

                item.set("Name", candidate)
                used.add(candidate.lower())
                suffix_by_base[base] = next_suffix + 1
                changed = True
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S009] renamed duplicate ReportItem names")

    def _fix_invalid_report_parameter_names(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            seen: set[str] = set()
            suffix_by_base: dict[str, int] = {}

            for param in root.xpath(".//*[local-name()='ReportParameter']"):
                name = str(param.get("Name", "")).strip()
                if not name:
                    continue
                base = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
                if not base:
                    base = "Param"
                if not re.match(r"^[A-Za-z_]", base):
                    base = f"_{base}"

                next_suffix = suffix_by_base.get(base, 1)
                candidate = base if next_suffix == 1 else f"{base}_{next_suffix}"
                while candidate.lower() in seen:
                    next_suffix += 1
                    candidate = f"{base}_{next_suffix}"
                suffix_by_base[base] = next_suffix + 1

                if candidate != name:
                    param.set("Name", candidate)
                    changed = True
                seen.add(candidate.lower())
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S008d] normalized ReportParameter names to CLS identifiers")

    def _fix_mismatched_parameter_layout(self, rdl: str, issue: Issue) -> str:
        def mutator(root: etree._Element) -> bool:
            changed = False
            for layout in root.xpath(".//*[local-name()='ReportParametersLayout']"):
                parent = layout.getparent()
                if parent is not None:
                    parent.remove(layout)
                    changed = True
            return changed

        return self._apply_xml_fix(rdl, mutator, "[S008e] removed inconsistent ReportParametersLayout")
