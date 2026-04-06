from __future__ import annotations

from typing import Any, Protocol

from viz_agent.validators.contracts import ValidationIssueV2


class Validator(Protocol):
    name: str

    def validate(self, data: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssueV2]:
        ...

