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

    def _collect_param_names(self, root: etree._Element) -> set[str]:
        return {p.get("Name", "") for p in root.findall(".//r:ReportParameter", self.ns)}
