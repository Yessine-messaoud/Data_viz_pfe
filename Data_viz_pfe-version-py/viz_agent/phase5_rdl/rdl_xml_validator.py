from __future__ import annotations

import re

from lxml import etree

from viz_agent.models.validation import Issue, ValidationReport

RDL_NAMESPACE = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RDL_NAMESPACE_2008 = "http://schemas.microsoft.com/sqlserver/reporting/2008/01/reportdefinition"
RDL_NAMESPACE_2010 = "http://schemas.microsoft.com/sqlserver/reporting/2010/01/reportdefinition"
VALID_NAMESPACES = {RDL_NAMESPACE, RDL_NAMESPACE_2008, RDL_NAMESPACE_2010}


class RDLXMLValidator:
    def validate(self, rdl_content: str | bytes) -> ValidationReport:
        errors: list[Issue] = []
        warnings: list[Issue] = []

        rdl_bytes = rdl_content.encode("utf-8") if isinstance(rdl_content, str) else rdl_content
        parser = etree.XMLParser(recover=False)

        try:
            root = etree.fromstring(rdl_bytes, parser=parser)
        except etree.XMLSyntaxError as exc:
            return ValidationReport(
                score=0,
                errors=[
                    Issue(
                        code="X001",
                        severity="error",
                        message=f"Malformed XML: {exc.msg} (line {exc.lineno}, col {exc.offset})",
                        fix="Check unclosed tags and escape special characters",
                    )
                ],
                warnings=warnings,
                can_proceed=False,
            )

        ns = root.nsmap.get(None) or root.nsmap.get("rd")
        if ns not in VALID_NAMESPACES or ns != RDL_NAMESPACE:
            errors.append(
                Issue(
                    code="X002",
                    severity="error",
                    message=f"Invalid or missing RDL namespace: '{ns}' (expected {RDL_NAMESPACE})",
                    fix="Set the default xmlns on <Report> to the RDL 2016 namespace",
                    auto_fix=RDL_NAMESPACE,
                )
            )

        local_name = etree.QName(root.tag).localname
        if local_name != "Report":
            errors.append(
                Issue(
                    code="X003",
                    severity="error",
                    message=f"Invalid root element '{local_name}' (expected 'Report')",
                    fix="Use <Report> as the XML root element",
                )
            )

        if rdl_bytes.startswith(b"<?xml"):
            decl = rdl_bytes[:120].decode("ascii", errors="replace")
            if "encoding" in decl and "utf-8" not in decl.lower():
                warnings.append(
                    Issue(
                        code="X004",
                        severity="warning",
                        message="XML declaration encoding is not UTF-8",
                        fix="Use encoding='utf-8'",
                    )
                )

        raw_text = rdl_content if isinstance(rdl_content, str) else rdl_content.decode("utf-8", errors="replace")
        ctrl_chars = re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", raw_text)
        if ctrl_chars:
            errors.append(
                Issue(
                    code="X005",
                    severity="error",
                    message=f"Forbidden control characters detected: {sorted(set(ctrl_chars))}",
                    fix="Remove forbidden control characters",
                    auto_fix="strip_control_chars",
                )
            )

        bad_attrs = re.findall(r'="[^"]*[<>&][^"]*"', raw_text)
        if bad_attrs:
            warnings.append(
                Issue(
                    code="X006",
                    severity="warning",
                    message=f"{len(bad_attrs)} attribute value(s) may contain unescaped XML characters",
                    fix="Escape < > & in XML attributes",
                    auto_fix="escape_attrs",
                )
            )

        score = max(0, 100 - len(errors) * 30 - len(warnings) * 5)
        return ValidationReport(score=score, errors=errors, warnings=warnings, can_proceed=len(errors) == 0)
