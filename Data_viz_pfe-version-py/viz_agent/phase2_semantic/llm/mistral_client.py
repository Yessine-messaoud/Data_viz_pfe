from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    column: str | None
    possible_meaning: str | None
    mapped_business_term: str | None
    confidence: float
    raw: Dict[str, Any]
    error: str | None = None


def _fallback(prompt: str) -> LLMResponse:
    logger.warning("LLM fallback used (no valid API key or request failure)")
    return LLMResponse(
        column=None,
        possible_meaning=None,
        mapped_business_term=None,
        confidence=0.0,
        raw={"prompt": prompt},
        error="fallback",
    )


def call_mistral(prompt: str, timeout: int = 10) -> LLMResponse:
    _ = timeout
    try:
        from viz_agent.phase2_semantic.llm_fallback_client import LLMFallbackClient, load_llm_keys_from_file

        load_llm_keys_from_file()
        llm_client = LLMFallbackClient.from_env()
        parsed = llm_client.chat_json(system_prompt="You return JSON only.", user_prompt=prompt)
        return LLMResponse(
            column=parsed.get("column"),
            possible_meaning=parsed.get("possible_meaning"),
            mapped_business_term=parsed.get("mapped_business_term"),
            confidence=float(parsed.get("confidence", 0) or 0),
            raw=parsed,
            error=None,
        )
    except Exception as exc:  # pragma: no cover - network dependent
        logger.error("LLM fallback chain failed: %s", exc)
        return _fallback(prompt)
