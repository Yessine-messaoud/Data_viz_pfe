from __future__ import annotations

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport


class RDLStructureValidator:
    ALLOWED_REPORT_ITEM_NAMES = {
        "Line",
        "Rectangle",
        "Textbox",
        "Image",
        "Subreport",
        "Chart",
        "GaugePanel",
        "Map",
        "Tablix",
        "CustomReportItem",
    }

    def validate(self, rdl_xml: str) -> ValidationReport:
        errors: list[Issue] = []
        warnings: list[Issue] = []

        if "```" in rdl_xml:
            errors.append(
                Issue(
                    code="RDL-STRUCT-001",
                    severity="error",
                    message="RDL contains markdown code fences",
                )
            )
            return ValidationReport(score=0, errors=errors, warnings=warnings, can_proceed=False)

        try:
            root = etree.fromstring(rdl_xml.encode("utf-8"))
        except etree.XMLSyntaxError as exc:
            return ValidationReport(
                score=0,
                errors=[Issue(code="RDL-STRUCT-XML", severity="error", message=f"Invalid XML: {exc}")],
                warnings=warnings,
                can_proceed=False,
            )

        ns = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}

        required = [
            "r:DataSources/r:DataSource",
            "r:DataSets/r:DataSet",
            "r:ReportSections/r:ReportSection/r:Body/r:ReportItems",
            "r:ReportSections/r:ReportSection/r:Body/r:Height",
            "r:ReportSections/r:ReportSection/r:Width",
            "r:ReportSections/r:ReportSection/r:Page",
        ]
        for path in required:
            if root.find(path, ns) is None:
                errors.append(
                    Issue(
                        code="RDL-STRUCT-REQ",
                        severity="error",
                        message=f"Missing required element: {path}",
                    )
                )

        dataset_names = []
        for ds in root.findall(".//r:DataSet", ns):
            name = ds.get("Name", "")
            if not name:
                errors.append(Issue(code="RDL-STRUCT-DSNAME", severity="error", message="DataSet without Name"))
            dataset_names.append(name)

            query = ds.find("r:Query/r:CommandText", ns)
            if query is None or not (query.text or "").strip():
                errors.append(
                    Issue(
                        code="RDL-STRUCT-DSQUERY",
                        severity="error",
                        message=f"DataSet '{name}' missing Query/CommandText",
                    )
                )

            for field in ds.findall("r:Fields/r:Field", ns):
                for child in list(field):
                    qname = etree.QName(child.tag)
                    if qname.namespace == ns["r"] and qname.localname not in {"DataField", "Value"}:
                        errors.append(
                            Issue(
                                code="RDL-STRUCT-FIELD",
                                severity="error",
                                message=(
                                    f"Field '{field.get('Name', '')}' contains invalid child '{qname.localname}' "
                                    "in reportdefinition namespace"
                                ),
                            )
                        )

        if len(dataset_names) != len(set(dataset_names)):
            errors.append(
                Issue(
                    code="RDL-STRUCT-DSDUP",
                    severity="error",
                    message="Duplicate DataSet names found",
                )
            )

        report_items = root.find("r:ReportSections/r:ReportSection/r:Body/r:ReportItems", ns)
        if report_items is not None:
            children = list(report_items)
            if not children:
                errors.append(
                    Issue(
                        code="RDL-STRUCT-ITEMS",
                        severity="error",
                        message="ReportItems is empty",
                    )
                )
            item_names = set()
            for child in children:
                qname = etree.QName(child.tag)
                if qname.namespace == ns["r"] and qname.localname not in self.ALLOWED_REPORT_ITEM_NAMES:
                    errors.append(
                        Issue(
                            code="RDL-STRUCT-ITEMTYPE",
                            severity="error",
                            message=f"Invalid ReportItems child '{qname.localname}'",
                        )
                    )
                item_name = child.get("Name")
                if item_name:
                    if item_name in item_names:
                        errors.append(
                            Issue(
                                code="RDL-STRUCT-ITEMDUP",
                                severity="error",
                                message=f"Duplicate report item Name '{item_name}'",
                            )
                        )
                    item_names.add(item_name)

            dataset_set = set(dataset_names)
            for node in root.findall(".//r:Tablix", ns) + root.findall(".//r:Chart", ns) + root.findall(".//r:Map", ns):
                ds_ref = node.findtext("r:DataSetName", namespaces=ns)
                if ds_ref and ds_ref not in dataset_set:
                    errors.append(
                        Issue(
                            code="RDL-STRUCT-BIND",
                            severity="error",
                            message=f"{etree.QName(node.tag).localname} references unknown DataSet '{ds_ref}'",
                        )
                    )

        score = max(0, 100 - len(errors) * 15 - len(warnings) * 5)
        return ValidationReport(score=score, errors=errors, warnings=warnings, can_proceed=len(errors) == 0)
