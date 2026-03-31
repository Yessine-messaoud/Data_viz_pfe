from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL_NAME = "mistral-small-latest"


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
    api_key = os.getenv("MISTRAL_API_KEY", API_KEY).strip()
    if not api_key:
        return _fallback(prompt)

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You return JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        resp = requests.post(MISTRAL_URL, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return LLMResponse(
            column=parsed.get("column"),
            possible_meaning=parsed.get("possible_meaning"),
            mapped_business_term=parsed.get("mapped_business_term"),
            confidence=float(parsed.get("confidence", 0) or 0),
            raw=parsed,
            error=None,
        )
    except Exception as exc:  # pragma: no cover - network dependent
        logger.error("Mistral call failed: %s", exc)
        return _fallback(prompt)
