from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any

from viz_agent.phase2_semantic.llm_fallback_client import LLMFallbackClient, load_llm_keys_from_file


@dataclass
class LLMFixResult:
    applied: bool
    fix_name: str = ""
    notes: list[str] = field(default_factory=list)


class LLMFallbackCorrectionEngine:
    """Optional LLM correction layer applied only after deterministic+heuristic retries fail."""

    def __init__(self, *, enabled: bool | None = None, llm_client: Any | None = None) -> None:
        env_enabled = os.getenv("VIZ_AGENT_ENABLE_LLM_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.enabled = env_enabled if enabled is None else bool(enabled)
        self._llm_client = llm_client

    def apply(
        self,
        phase_name: str,
        state: dict[str, Any],
        errors: list[str],
        *,
        attempt: int,
    ) -> LLMFixResult:
        if not self.enabled:
            return LLMFixResult(applied=False, fix_name="disabled", notes=["LLM fallback disabled"])

        client = self._ensure_client()
        if client is None:
            return LLMFixResult(applied=False, fix_name="unavailable", notes=["No LLM provider available"])

        context = state.setdefault("context", {}) if isinstance(state, dict) else {}
        llm_hints = context.setdefault("llm_fixes", {}) if isinstance(context, dict) else {}
        phase_hints: dict[str, Any] = llm_hints.setdefault(phase_name, {}) if isinstance(llm_hints, dict) else {}

        system_prompt = (
            "You are a BI pipeline repair assistant. "
            "Return strict JSON with keys: fix_name (string), hints (object), notes (array of strings)."
        )
        user_prompt = (
            f"Phase: {phase_name}\n"
            f"Attempt: {attempt}\n"
            f"Errors: {errors}\n"
            "Propose minimal deterministic hints that help next retry succeed."
        )

        try:
            payload = client.chat_json(system_prompt, user_prompt)
        except Exception as exc:
            return LLMFixResult(applied=False, fix_name="llm_error", notes=[str(exc)])

        hints = payload.get("hints") if isinstance(payload, dict) else None
        if not isinstance(hints, dict) or not hints:
            return LLMFixResult(applied=False, fix_name="empty_hints", notes=["LLM returned no actionable hints"])

        for key, value in hints.items():
            phase_hints[str(key)] = value

        fix_name = str(payload.get("fix_name") or "llm_fix")
        notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
        return LLMFixResult(applied=True, fix_name=fix_name, notes=[str(n) for n in notes])

    def _ensure_client(self) -> Any | None:
        if self._llm_client is not None:
            return self._llm_client
        try:
            load_llm_keys_from_file()
            self._llm_client = LLMFallbackClient.from_env()
            return self._llm_client
        except Exception:
            return None
