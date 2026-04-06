from __future__ import annotations

from typing import Any

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport
from viz_agent.phase5_rdl.rules.expression_parser import extract_field_refs

NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _field_name(ref: Any) -> str:
    if isinstance(ref, dict):
        return str(ref.get("column") or ref.get("name") or "").strip()
    return str(getattr(ref, "column", "") or getattr(ref, "name", "") or ref or "").strip()


def _dataset_fields(dataset: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in getattr(dataset, "fields", []) or []:
        field_dict = _as_dict(field)
        name = str(field_dict.get("name") or getattr(field, "name", "") or "").strip()
        if not name:
            continue
        out[name.lower()] = name
    return out


class RDLDatasetValidator:
    def validate(self, datasets: list[Any], visuals: list[Any], semantic_model: Any | None = None) -> ValidationReport:
        issues: list[Issue] = []
        warnings: list[Issue] = []

        if not datasets:
            issues.append(Issue(code="D001", severity="error", message="No RDL datasets were generated"))
            return ValidationReport(score=0, errors=issues, warnings=warnings, can_proceed=False)

        dataset_map = {str(getattr(dataset, "name", "") or "").lower(): dataset for dataset in datasets if str(getattr(dataset, "name", "") or "").strip()}

        for index, dataset in enumerate(datasets):
            dataset_name = str(getattr(dataset, "name", "") or "").strip()
            if not dataset_name:
                issues.append(Issue(code="D002", severity="error", message=f"Dataset at index {index} has no name"))
                continue

            fields = getattr(dataset, "fields", []) or []
            if not fields:
                issues.append(Issue(code="D003", severity="error", message=f"Dataset '{dataset_name}' has no fields"))
                continue

            field_names = _dataset_fields(dataset)
            if len(field_names) != len({name.lower() for name in field_names.values()}):
                issues.append(Issue(code="D004", severity="error", message=f"Dataset '{dataset_name}' contains duplicate fields"))

            query = str(getattr(dataset, "query", "") or "").strip()
            if not query:
                issues.append(Issue(code="D005", severity="error", message=f"Dataset '{dataset_name}' has empty query"))
            if "SELECT *" in query.upper():
                issues.append(Issue(code="D006", severity="error", message=f"Dataset '{dataset_name}' contains forbidden SELECT *"))

        for visual in visuals:
            visual_id = str(getattr(visual, "id", "") or getattr(visual, "source_worksheet", "") or "visual").strip()
            dataset_name = str(getattr(visual, "dataset_name", "") or getattr(visual, "dataset", "") or "").strip()
            if not dataset_name:
                warnings.append(Issue(code="D100", severity="warning", message=f"Visual '{visual_id}' has no dataset assignment"))
                continue
            dataset = dataset_map.get(dataset_name.lower())
            if dataset is None:
                issues.append(Issue(code="D101", severity="error", message=f"Visual '{visual_id}' references unknown dataset '{dataset_name}'"))
                continue

            dataset_fields = _dataset_fields(dataset)
            binding = _as_dict(getattr(visual, "data_binding", {}))
            axes = _as_dict(binding.get("axes"))
            if not axes and str(getattr(visual, "type", "") or "").strip().lower() not in {"kpi", "textbox"}:
                issues.append(Issue(code="D102", severity="error", message=f"Visual '{visual_id}' has no axes"))

            referenced_fields: list[tuple[str, str]] = []
            for axis_name, ref in axes.items():
                field_name = _field_name(ref)
                if not field_name:
                    continue
                referenced_fields.append((axis_name, field_name))
                if field_name.lower() not in dataset_fields:
                    issues.append(Issue(code="D103", severity="error", message=f"Visual '{visual_id}' references missing field '{field_name}' in dataset '{dataset_name}'"))

            visual_type = str(getattr(visual, "type", "") or "").strip().lower()
            if visual_type == "bar":
                if not any(name == "x" for name, _ in referenced_fields):
                    issues.append(Issue(code="D104", severity="error", message=f"Bar visual '{visual_id}' requires x axis"))
                if not any(name in {"y", "size"} for name, _ in referenced_fields):
                    issues.append(Issue(code="D105", severity="error", message=f"Bar visual '{visual_id}' requires y measure"))
            elif visual_type == "treemap":
                if not any(name == "group" for name, _ in referenced_fields):
                    issues.append(Issue(code="D106", severity="error", message=f"Treemap visual '{visual_id}' requires group dimension"))
                if not any(name == "size" for name, _ in referenced_fields):
                    issues.append(Issue(code="D107", severity="error", message=f"Treemap visual '{visual_id}' requires size measure"))
            elif visual_type == "kpi":
                if not any(name in {"y", "measure"} for name, _ in referenced_fields):
                    issues.append(Issue(code="D108", severity="error", message=f"KPI visual '{visual_id}' requires one measure"))

        score = max(0, 100 - len(issues) * 12 - len(warnings) * 4)
        return ValidationReport(score=score, errors=issues, warnings=warnings, can_proceed=len(issues) == 0)

    def validate_rendering_contract(self, root: etree._Element) -> ValidationReport:
        issues: list[Issue] = []
        warnings: list[Issue] = []
        ns = {"r": NS}
        dataset_names = {ds.get("Name", "") for ds in root.findall(".//r:DataSet", ns)}
        dataset_fields: dict[str, set[str]] = {}
        for ds in root.findall(".//r:DataSet", ns):
            ds_name = str(ds.get("Name", "") or "").strip()
            fields = {
                str(field.get("Name", "") or "").strip()
                for field in ds.findall("r:Fields/r:Field", ns)
                if str(field.get("Name", "") or "").strip()
            }
            dataset_fields[ds_name] = fields
            if not fields:
                issues.append(Issue(code="R102", severity="error", message=f"DataSet '{ds_name}' has no Fields definitions"))

        for node in root.findall(".//r:Tablix", ns) + root.findall(".//r:Chart", ns) + root.findall(".//r:Map", ns) + root.findall(".//r:Textbox", ns):
            name = node.get("Name", "<no-name>")
            ds_name = (node.findtext("r:DataSetName", default="", namespaces=ns) or "").strip()
            if node.tag.endswith("Textbox"):
                continue
            if not ds_name:
                issues.append(Issue(code="R100", severity="error", message=f"{etree.QName(node.tag).localname} '{name}' missing DataSetName"))
            elif ds_name not in dataset_names:
                issues.append(Issue(code="R101", severity="error", message=f"{etree.QName(node.tag).localname} '{name}' references unknown dataset '{ds_name}'"))
                continue

            declared_fields = dataset_fields.get(ds_name, set())
            for text_node in node.xpath(".//text()"):
                for field_ref in extract_field_refs(str(text_node or "")):
                    if field_ref not in declared_fields:
                        issues.append(
                            Issue(
                                code="R103",
                                severity="error",
                                message=(
                                    f"{etree.QName(node.tag).localname} '{name}' references field '{field_ref}' "
                                    f"missing from DataSet '{ds_name}'"
                                ),
                            )
                        )

            if node.tag.endswith("Chart"):
                has_category = bool(
                    node.xpath(
                        ".//*[local-name()='ChartCategoryHierarchy']//*[local-name()='Label' or local-name()='GroupExpression']"
                    )
                )
                has_value = bool(node.xpath(".//*[local-name()='ChartDataPointValues']//*[local-name()='Y']"))
                if not has_category:
                    issues.append(
                        Issue(
                            code="R104",
                            severity="error",
                            message=f"Chart '{name}' missing category grouping definition",
                        )
                    )
                if not has_value:
                    issues.append(
                        Issue(
                            code="R105",
                            severity="error",
                            message=f"Chart '{name}' missing Y value definition",
                        )
                    )

        score = max(0, 100 - len(issues) * 15 - len(warnings) * 5)
        return ValidationReport(score=score, errors=issues, warnings=warnings, can_proceed=len(issues) == 0)
