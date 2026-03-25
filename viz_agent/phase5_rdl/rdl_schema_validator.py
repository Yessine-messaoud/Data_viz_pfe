from __future__ import annotations

import re

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport
from viz_agent.phase5_rdl.rules.enum_values import NUMERIC_ELEMENTS, VALID_ENUMS
from viz_agent.phase5_rdl.rules.required_elements import (
    DATASOURCE_REQUIRED_CHILDREN,
    DATASET_REQUIRED_CHILDREN,
    FIELD_REQUIRED_CHILDREN,
    QUERY_REQUIRED_CHILDREN,
    REPORT_REQUIRED_PATHS,
    TABLIX_REQUIRED_CHILDREN,
)

NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"


class RDLSchemaValidator:
    def __init__(self) -> None:
        self.ns = {"r": NS}

    def validate(self, root: etree._Element) -> ValidationReport:
        errors: list[Issue] = []
        warnings: list[Issue] = []

        for path in REPORT_REQUIRED_PATHS:
            if root.find(path, self.ns) is None:
                errors.append(
                    Issue(
                        code="S001",
                        severity="error",
                        message=f"Missing required element: {path}",
                        fix="Generate required top-level RDL sections",
                    )
                )

        datasource_names = {ds.get("Name", "") for ds in root.findall(".//r:DataSource", self.ns)}

        for ds in root.findall(".//r:DataSource", self.ns):
            ds_name = ds.get("Name", "<no-name>")
            self._check_required_children(ds, DATASOURCE_REQUIRED_CHILDREN, f"DataSource[{ds_name}]", "S002", errors)
            conn = ds.find("r:ConnectionProperties/r:ConnectString", self.ns)
            if conn is None or not (conn.text or "").strip():
                warnings.append(
                    Issue(
                        code="S002b",
                        severity="warning",
                        message=f"DataSource '{ds_name}' has empty ConnectString",
                        fix="Provide a placeholder ConnectString if runtime binding is external",
                    )
                )

        dataset_names: list[str] = []
        for ds in root.findall(".//r:DataSet", self.ns):
            ds_name = ds.get("Name", "")
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", ds_name or ""):
                errors.append(
                    Issue(
                        code="S003n",
                        severity="error",
                        message=f"DataSet name '{ds_name}' is not CLS-compliant",
                        fix="Use only letters, digits, and underscores, starting with a letter or underscore",
                    )
                )
            dataset_names.append(ds_name)

            self._check_required_children(ds, DATASET_REQUIRED_CHILDREN, f"DataSet[{ds_name}]", "S003", errors)

            query = ds.find("r:Query", self.ns)
            if query is not None:
                self._check_required_children(query, QUERY_REQUIRED_CHILDREN, f"DataSet[{ds_name}]/Query", "S003b", errors)
                dsn = query.find("r:DataSourceName", self.ns)
                if dsn is not None and (dsn.text or "").strip() not in datasource_names:
                    errors.append(
                        Issue(
                            code="S003c",
                            severity="error",
                            message=(
                                f"DataSet '{ds_name}' references unknown DataSourceName '{(dsn.text or '').strip()}'"
                            ),
                            fix="Ensure DataSourceName points to an existing DataSource Name",
                        )
                    )

            for field in ds.findall("r:Fields/r:Field", self.ns):
                field_name = field.get("Name", "<no-name>")
                self._check_required_children(field, FIELD_REQUIRED_CHILDREN, f"Field[{field_name}]", "S003d", errors)

        if len(set(dataset_names)) != len(dataset_names):
            errors.append(
                Issue(
                    code="S003e",
                    severity="error",
                    message="Duplicate DataSet names detected",
                    fix="Ensure each DataSet/@Name is unique",
                )
            )

        report_items = root.find("r:ReportSections/r:ReportSection/r:Body/r:ReportItems", self.ns)
        if report_items is None or len(list(report_items)) == 0:
            errors.append(
                Issue(
                    code="S004",
                    severity="error",
                    message="Body/ReportItems is missing or empty",
                    fix="Add at least one ReportItem (Tablix, Textbox, Chart, ...)",
                )
            )

        for tablix in root.findall(".//r:Tablix", self.ns):
            tname = tablix.get("Name", "<no-name>")
            self._check_required_children(tablix, TABLIX_REQUIRED_CHILDREN, f"Tablix[{tname}]", "S005", errors)

        for chart_member in root.findall(".//r:ChartMember", self.ns):
            if chart_member.find("r:Label", self.ns) is None:
                errors.append(
                    Issue(
                        code="S005c",
                        severity="error",
                        message="ChartMember missing required Label",
                        fix="Add <Label> under each ChartMember",
                    )
                )

        for elem in root.iter():
            if not isinstance(elem.tag, str):
                continue
            local = etree.QName(elem.tag).localname
            if local in VALID_ENUMS:
                val = (elem.text or "").strip()
                if val and val not in VALID_ENUMS[local]:
                    errors.append(
                        Issue(
                            code="S006",
                            severity="error",
                            message=f"Invalid enum value for {local}: '{val}'",
                            fix=f"Use one of: {sorted(VALID_ENUMS[local])}",
                            auto_fix="enum_case",
                        )
                    )
            if local in NUMERIC_ELEMENTS:
                val = (elem.text or "").strip()
                if val and not self._is_valid_dimension(val):
                    errors.append(
                        Issue(
                            code="S007",
                            severity="error",
                            message=f"Invalid dimension '{val}' in <{local}>",
                            fix="Use values such as 8.5in, 2cm, 15pt",
                            auto_fix="add_unit",
                        )
                    )

        for param in root.findall(".//r:ReportParameter", self.ns):
            pname = param.get("Name", "<no-name>")
            dtype = param.find("r:DataType", self.ns)
            if dtype is None:
                errors.append(
                    Issue(
                        code="S008",
                        severity="error",
                        message=f"ReportParameter '{pname}' missing DataType",
                        fix="Add <DataType>String</DataType> or another valid data type",
                    )
                )
            elif (dtype.text or "").strip() not in VALID_ENUMS["DataType"]:
                errors.append(
                    Issue(
                        code="S008b",
                        severity="error",
                        message=f"ReportParameter '{pname}' has invalid DataType '{(dtype.text or '').strip()}'",
                        fix=f"Use one of: {sorted(VALID_ENUMS['DataType'])}",
                    )
                )

        score = max(0, 100 - len(errors) * 12 - len(warnings) * 4)
        return ValidationReport(score=score, errors=errors, warnings=warnings, can_proceed=len(errors) == 0)

    def _check_required_children(
        self,
        parent: etree._Element,
        required: list[str],
        parent_label: str,
        code: str,
        errors: list[Issue],
    ) -> None:
        for child in required:
            if parent.find(f"r:{child}", self.ns) is None:
                errors.append(
                    Issue(
                        code=code,
                        severity="error",
                        message=f"{parent_label} missing required child '{child}'",
                        fix=f"Add <{child}> under {parent_label}",
                    )
                )

    @staticmethod
    def _is_valid_dimension(value: str) -> bool:
        return bool(re.match(r"^-?\d+(\.\d+)?(in|cm|mm|pt|pc|%)$", value.strip()))
