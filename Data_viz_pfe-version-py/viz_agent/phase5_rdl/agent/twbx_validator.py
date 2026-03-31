"""
TWBXValidator: Validation des fichiers TWBX générés
"""
from typing import Any
import zipfile
import io
import xml.etree.ElementTree as ET

class TWBXValidator:
    def validate(self, content: bytes) -> Dict:
        errors = []
        warnings = []
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(content))
            if "workbook.twb" not in zip_file.namelist():
                errors.append("Missing required file: workbook.twb")
            # ... autres validations ...
        except zipfile.BadZipFile:
            errors.append("Invalid ZIP archive")
        return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings}
