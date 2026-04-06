from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from viz_agent.validators.contracts import ValidationIssueV2

try:
    import jsonschema
except Exception:  # pragma: no cover - optional dependency
    jsonschema = None  # type: ignore


class StructuralValidator:
    name = "structural"

    def __init__(self, schema_root: Path | None = None):
        self.schema_root = schema_root or Path(__file__).resolve().parents[1] / "schemas"

    def _load_schema(self, filename: str) -> dict[str, Any]:
        path = self.schema_root / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def validate(self, data: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssueV2]:
        issues: list[ValidationIssueV2] = []

        if jsonschema is None:
            issues.append(
                ValidationIssueV2(
                    type="structural",
                    severity="warning",
                    code="ST000",
                    message="jsonschema indisponible: validation structurelle schema skippee.",
                    location="$",
                    suggestion="Installer jsonschema pour activer les controles schema stricts.",
                )
            )
            return issues

        if "dashboard_spec" in data:
            spec_schema = self._load_schema("abstract_spec.schema.json")
            issues.extend(self._validate_schema(data, spec_schema, "$"))

        semantic = context.get("semantic_model")
        if isinstance(semantic, dict) and semantic:
            sem_schema = self._load_schema("semantic_model.schema.json")
            issues.extend(self._validate_schema(semantic, sem_schema, "context.semantic_model"))

        return issues

    def _validate_schema(self, payload: dict[str, Any], schema: dict[str, Any], root_location: str) -> list[ValidationIssueV2]:
        assert jsonschema is not None
        issues: list[ValidationIssueV2] = []
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
            pointer = ".".join(str(part) for part in err.path)
            location = f"{root_location}.{pointer}" if pointer else root_location
            issues.append(
                ValidationIssueV2(
                    type="structural",
                    severity="error",
                    code="ST001",
                    message=err.message,
                    location=location,
                    suggestion="Aligner le payload sur le schema JSON de la phase.",
                )
            )
        return issues

