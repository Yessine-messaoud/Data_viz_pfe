from __future__ import annotations

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport
from viz_agent.phase5_rdl.rules.expression_parser import extract_field_refs, extract_param_refs

NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"


class RDLSemanticValidator:
    def __init__(self) -> None:
        self.ns = {"r": NS}

    def validate(self, root: etree._Element) -> ValidationReport:
        errors: list[Issue] = []
        warnings: list[Issue] = []

        datasource_names = self._collect_datasource_names(root)
        dataset_names = self._collect_dataset_names(root)
        dataset_fields = self._collect_dataset_fields(root)
        dataset_field_types = self._collect_dataset_field_types(root)
        param_names = self._collect_param_names(root)

        for node in root.findall(".//r:Tablix", self.ns) + root.findall(".//r:Chart", self.ns) + root.findall(".//r:Map", self.ns):
            node_name = node.get("Name", "<no-name>")
            dsn = (node.findtext("r:DataSetName", default="", namespaces=self.ns) or "").strip()
            if dsn and dsn not in dataset_names:
                errors.append(
                    Issue(
                        code="SEM001",
                        severity="error",
                        message=f"{etree.QName(node.tag).localname} '{node_name}' references unknown DataSet '{dsn}'",
                        fix="Set DataSetName to an existing DataSet/@Name",
                    )
                )

        for node in root.findall(".//r:Tablix", self.ns) + root.findall(".//r:Chart", self.ns) + root.findall(".//r:Map", self.ns):
            dsn = (node.findtext("r:DataSetName", default="", namespaces=self.ns) or "").strip()
            declared = dataset_fields.get(dsn, set())
            if dsn and not declared:
                errors.append(
                    Issue(
                        code="SEM005",
                        severity="error",
                        message=f"DataSet '{dsn}' has no declared fields",
                        fix="Populate DataSet/Fields with at least one Field/DataField",
                    )
                )

            if node.tag.endswith("Chart") and dsn:
                self._validate_chart_measures(node, dsn, dataset_field_types.get(dsn, {}), errors)
                self._validate_chart_dimensions(node, dsn, dataset_field_types.get(dsn, {}), errors)

            for elem in node.iter():
                text = (elem.text or "").strip()
                for field_name in extract_field_refs(text):
                    if dsn and field_name not in declared:
                        errors.append(
                            Issue(
                                code="SEM002",
                                severity="error",
                                message=(
                                    f"Expression references unknown field '{field_name}' for DataSet '{dsn}'"
                                ),
                                fix="Align =Fields!X.Value expressions with DataSet/Fields definitions",
                            )
                        )

        for elem in root.iter():
            text = (elem.text or "").strip()
            for pname in extract_param_refs(text):
                if pname not in param_names:
                    warnings.append(
                        Issue(
                            code="SEM003",
                            severity="warning",
                            message=f"Expression references unknown parameter '{pname}'",
                            fix="Add ReportParameter or update the expression",
                        )
                    )

        for ds_name in datasource_names:
            used = False
            for query_dsn in root.findall(".//r:DataSet/r:Query/r:DataSourceName", self.ns):
                if (query_dsn.text or "").strip() == ds_name:
                    used = True
                    break
            if not used:
                warnings.append(
                    Issue(
                        code="SEM004",
                        severity="warning",
                        message=f"DataSource '{ds_name}' is not referenced by any DataSet",
                        fix="Remove unused DataSource or map a DataSet Query/DataSourceName to it",
                    )
                )

        for ds in root.findall(".//r:DataSet", self.ns):
            ds_name = ds.get("Name", "<no-name>")
            cmd = ds.find("r:Query/r:CommandText", self.ns)
            if cmd is None or not (cmd.text or "").strip():
                errors.append(
                    Issue(
                        code="SEM007",
                        severity="error",
                        message=f"DataSet '{ds_name}' has empty Query/CommandText",
                        fix="Provide a non-empty SQL command",
                    )
                )

            for field in ds.findall("r:Fields/r:Field", self.ns):
                field_name = field.get("Name", "")
                type_name = (field.findtext("rd:TypeName", default="", namespaces={**self.ns, "rd": "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"}) or "").strip().lower()
                if type_name in {"decimal", "integer", "int", "float", "double", "money"}:
                    continue
                if field_name.lower().startswith(("sum", "avg", "count", "total", "amount", "value")):
                    warnings.append(
                        Issue(
                            code="SEM008",
                            severity="warning",
                            message=f"Field '{field_name}' in DataSet '{ds_name}' looks like a measure but is typed as '{type_name or 'unknown'}'",
                            fix="Prefer numeric TypeName for aggregate measures",
                        )
                    )

        score = max(0, 100 - len(errors) * 10 - len(warnings) * 3)
        return ValidationReport(score=score, errors=errors, warnings=warnings, can_proceed=len(errors) == 0)

    def _collect_datasource_names(self, root: etree._Element) -> set[str]:
        return {ds.get("Name", "") for ds in root.findall(".//r:DataSource", self.ns)}

    def _collect_dataset_names(self, root: etree._Element) -> set[str]:
        return {ds.get("Name", "") for ds in root.findall(".//r:DataSet", self.ns)}

    def _collect_dataset_fields(self, root: etree._Element) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for ds in root.findall(".//r:DataSet", self.ns):
            ds_name = ds.get("Name", "")
            fields = {f.get("Name", "") for f in ds.findall("r:Fields/r:Field", self.ns) if f.get("Name")}
            out[ds_name] = fields
        return out

    def _collect_dataset_field_types(self, root: etree._Element) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        ns = {**self.ns, "rd": "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"}
        for ds in root.findall(".//r:DataSet", self.ns):
            ds_name = ds.get("Name", "")
            field_types: dict[str, str] = {}
            for field in ds.findall("r:Fields/r:Field", self.ns):
                field_name = field.get("Name", "")
                if not field_name:
                    continue
                field_types[field_name] = (field.findtext("rd:TypeName", default="", namespaces=ns) or "").strip()
            out[ds_name] = field_types
        return out

    def _validate_chart_measures(self, node: etree._Element, dsn: str, field_types: dict[str, str], errors: list[Issue]) -> None:
        for field_ref in node.xpath(".//*[local-name()='Value']//text()"):
            for ref in extract_field_refs(str(field_ref or "")):
                type_name = field_types.get(ref, "").strip().lower()
                if type_name and type_name not in {"decimal", "integer", "int", "float", "double", "money"}:
                    errors.append(
                        Issue(
                            code="SEM009",
                            severity="error",
                            message=f"Chart '{node.get('Name', '<no-name>')}' uses non-numeric field '{ref}' from DataSet '{dsn}'",
                            fix="Bind chart value expressions to numeric measure fields",
                        )
                    )

    def _validate_chart_dimensions(self, node: etree._Element, dsn: str, field_types: dict[str, str], errors: list[Issue]) -> None:
        category_text_nodes = node.xpath(
            ".//*[local-name()='ChartCategoryHierarchy']//*[local-name()='Label']//text() "
            "| .//*[local-name()='ChartCategoryHierarchy']//*[local-name()='GroupExpression']//text()"
        )
        for text_node in category_text_nodes:
            for ref in extract_field_refs(str(text_node or "")):
                type_name = field_types.get(ref, "").strip().lower()
                if type_name in {"decimal", "integer", "int", "float", "double", "money"}:
                    errors.append(
                        Issue(
                            code="SEM010",
                            severity="error",
                            message=(
                                f"Chart '{node.get('Name', '<no-name>')}' uses numeric field '{ref}' "
                                f"as category/group dimension in DataSet '{dsn}'"
                            ),
                            fix="Bind chart category/grouping to a dimension (string/date) field",
                        )
                    )

    def _collect_param_names(self, root: etree._Element) -> set[str]:
        return {p.get("Name", "") for p in root.findall(".//r:ReportParameter", self.ns)}
