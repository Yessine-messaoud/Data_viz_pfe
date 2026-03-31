from __future__ import annotations

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport


class RDLValidator:
    REQUIRED_ELEMENTS = [
        "DataSources/DataSource",
        "DataSets/DataSet",
        "ReportSections/ReportSection/Body/ReportItems",
        "ReportSections/ReportSection/Page",
    ]

    def validate(self, rdl_xml: str) -> ValidationReport:
        errors: list[Issue] = []
        warnings: list[Issue] = []

        try:
            root = etree.fromstring(rdl_xml.encode("utf-8"))
        except etree.XMLSyntaxError as exc:
            return ValidationReport(
                errors=[Issue(code="R_XML", severity="error", message=f"XML invalide: {exc}")],
                can_proceed=False,
            )

        ns = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}

        for path in self.REQUIRED_ELEMENTS:
            current = root
            for part in path.split("/"):
                current = current.find(f"r:{part}", ns)
                if current is None:
                    errors.append(
                        Issue(
                            code="R_STRUCT",
                            severity="error",
                            message=f"Element RDL manquant: {path}",
                        )
                    )
                    break

        for dataset in root.findall(".//r:DataSet", ns):
            if dataset.find("r:Query", ns) is None:
                errors.append(
                    Issue(
                        code="R_DS",
                        severity="error",
                        message=f"DataSet '{dataset.get('Name')}' sans <Query>",
                    )
                )

        dataset_names = {ds.get("Name") for ds in root.findall(".//r:DataSet", ns)}
        for tablix in root.findall(".//r:Tablix", ns):
            ds_ref = tablix.findtext("r:DataSetName", namespaces=ns)
            if ds_ref and ds_ref not in dataset_names:
                errors.append(
                    Issue(
                        code="R_BIND",
                        severity="error",
                        message=f"Tablix '{tablix.get('Name')}' reference DataSet inconnu: {ds_ref}",
                    )
                )

        return ValidationReport(
            score=max(0, 100 - len(errors) * 20 - len(warnings) * 5),
            errors=errors,
            warnings=warnings,
            can_proceed=len(errors) == 0,
        )
