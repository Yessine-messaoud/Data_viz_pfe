from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SemanticRouter:
    threshold: float = 0.75

    def route(
        self,
        cache_hit: dict[str, Any] | None,
        fast_result: tuple[Any, Any, dict[str, Any]],
        llm_result_factory,
    ):
        if cache_hit is not None:
            return "cache", cache_hit

        fast_conf = float((fast_result[2].get("orchestration", {}) or {}).get("confidence", 0.0) or 0.0)
        if fast_conf >= self.threshold:
            return "fast", fast_result

        return "fallback", llm_result_factory()
