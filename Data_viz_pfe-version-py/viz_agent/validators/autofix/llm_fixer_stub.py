from __future__ import annotations

from copy import deepcopy
from typing import Any


class LLMAutoFixerStub:
    """Placeholder for future LLM-assisted fixes."""

    def apply(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        fixed = deepcopy(payload)
        return fixed, []

