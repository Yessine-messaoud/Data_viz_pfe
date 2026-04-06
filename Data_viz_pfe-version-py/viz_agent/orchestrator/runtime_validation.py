from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from viz_agent.orchestrator.runtime_error_normalizer import normalize_issue_object, normalize_runtime_error
from viz_agent.phase5_rdl.rdl_xml_validator import RDLXMLValidator


class RDLRuntimeValidator:
    """Local runtime validation for generated RDL files without external SSRS dependency."""

    def __init__(self, *, enable_schema_validation: bool = True) -> None:
        self.enable_schema_validation = bool(enable_schema_validation)
        self._xml_validator = RDLXMLValidator()

    def validate_file(self, rdl_path: str | Path) -> dict[str, Any]:
        path = Path(rdl_path)
        errors: list[dict[str, str]] = []

        if not path.exists():
            errors.append(
                normalize_runtime_error(
                    f"RDL file does not exist: {path}",
                    location=str(path),
                    severity="P1",
                )
            )
            return self._result(errors)

        try:
            payload = path.read_bytes()
        except Exception as exc:
            errors.append(normalize_runtime_error(f"Unable to read RDL file: {exc}", location=str(path), severity="P1"))
            return self._result(errors)

        xml_report = self._xml_validator.validate(payload)
        for issue in xml_report.errors:
            errors.append(normalize_issue_object(issue))

        root = None
        if not errors:
            try:
                root = etree.fromstring(payload)
            except Exception as exc:
                errors.append(normalize_runtime_error(f"XML parse failed while opening report: {exc}", severity="P1"))

        # Optional SSRS-compatible local checks when validator is available.
        if self.enable_schema_validation and root is not None:
            try:
                from viz_agent.phase5_rdl.rdl_schema_validator import RDLSchemaValidator

                schema_report = RDLSchemaValidator().validate(root)
                for issue in schema_report.errors:
                    errors.append(normalize_issue_object(issue))
            except Exception:
                # Optional check should never block runtime validator execution.
                pass

        if root is not None:
            errors.extend(self._simulate_opening_checks(root))

        return self._result(errors)

    def _simulate_opening_checks(self, root: etree._Element) -> list[dict[str, str]]:
        ns_uri = root.nsmap.get(None) or ""
        ns = {"r": ns_uri} if ns_uri else {}
        found_errors: list[dict[str, str]] = []

        def _missing(xpath: str) -> bool:
            if not ns:
                return root.find(xpath.replace("r:", "")) is None
            return root.find(xpath, ns) is None

        if _missing(".//r:DataSources"):
            found_errors.append(
                normalize_runtime_error(
                    "Missing required DataSources section for runtime loading",
                    location="DataSources",
                    severity="P1",
                )
            )

        if _missing(".//r:Body") or _missing(".//r:Body/r:ReportItems"):
            found_errors.append(
                normalize_runtime_error(
                    "Report body is incomplete; rendering cannot start",
                    location="Body/ReportItems",
                    severity="P1",
                )
            )

        return found_errors

    def _result(self, errors: list[dict[str, str]]) -> dict[str, Any]:
        if not errors:
            return {"status": "success", "errors": [], "confidence": 0.95}

        confidence = max(0.1, 1.0 - 0.2 * len(errors))
        return {
            "status": "failure",
            "errors": errors,
            "confidence": round(confidence, 3),
        }
