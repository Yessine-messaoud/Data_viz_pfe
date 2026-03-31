"""
RDLValidator: Validation des fichiers RDL générés
"""
from typing import Any
import xml.etree.ElementTree as ET

class RDLValidator:
    def validate(self, content: bytes) -> Dict:
        errors = []
        warnings = []
        try:
            root = ET.fromstring(content)
            if root.tag != "Report":
                errors.append("Root element must be 'Report'")
            # ... autres validations ...
        except ET.ParseError as e:
            errors.append(f"XML parsing error: {e}")
        return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}
