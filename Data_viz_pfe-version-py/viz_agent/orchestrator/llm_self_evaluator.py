from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

from viz_agent.phase2_semantic.llm_fallback_client import LLMFallbackClient, load_llm_keys_from_file


@dataclass
class SelfEvalResult:
    score: float
    issues: list[str] = field(default_factory=list)
    dimensions: dict[str, float] = field(default_factory=dict)
    provider: str = ""


class LLMSelfEvaluator:
    """Optional LLM-as-judge evaluator for phase3 and phase5 outputs."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        client: Any | None = None,
        phase3_threshold: float = 0.70,
        phase5_threshold: float = 0.75,
    ) -> None:
        env_enabled = os.getenv("VIZ_AGENT_ENABLE_LLM_SELF_EVAL", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.enabled = env_enabled if enabled is None else bool(enabled)
        self._client = client
        self.phase3_threshold = max(0.0, min(1.0, float(phase3_threshold)))
        self.phase5_threshold = max(0.0, min(1.0, float(phase5_threshold)))

    def evaluate_phase3(self, output: dict[str, Any]) -> SelfEvalResult:
        if not self.enabled:
            return SelfEvalResult(score=1.0, issues=[], dimensions={"skipped": 1.0}, provider="disabled")

        payload = output.get("abstract_spec") if isinstance(output, dict) else {}
        if not isinstance(payload, dict):
            return SelfEvalResult(score=0.0, issues=["Phase3 self-eval: abstract_spec missing"], provider="local")

        client = self._ensure_client()
        if client is None:
            # Deterministic fallback judge if LLM is unavailable.
            return self._deterministic_phase3(payload)

        system_prompt = (
            "You are an expert BI quality judge. "
            "Return strict JSON with keys: score (0..1), issues (array), dimensions (object with structural_validity, semantic_correctness, visual_coherence)."
        )
        user_prompt = (
            "Evaluate the Phase3 abstract specification for structural validity, semantic correctness and visual coherence. "
            f"JSON payload: {payload}"
        )
        return self._call_llm(client, system_prompt, user_prompt, default=self._deterministic_phase3(payload))

    def evaluate_phase5(self, output: dict[str, Any]) -> SelfEvalResult:
        if not self.enabled:
            return SelfEvalResult(score=1.0, issues=[], dimensions={"skipped": 1.0}, provider="disabled")

        payload = output.get("export_result") if isinstance(output, dict) else {}
        if not isinstance(payload, dict):
            return SelfEvalResult(score=0.0, issues=["Phase5 self-eval: export_result missing"], provider="local")

        client = self._ensure_client()
        if client is None:
            return self._deterministic_phase5(payload)

        system_prompt = (
            "You are an expert RDL quality judge. "
            "Return strict JSON with keys: score (0..1), issues (array), dimensions (object with structural_validity, semantic_correctness, visual_coherence)."
        )
        user_prompt = (
            "Evaluate the Phase5 export output for structural validity, semantic correctness and visual coherence. "
            f"JSON payload: {payload}"
        )
        return self._call_llm(client, system_prompt, user_prompt, default=self._deterministic_phase5(payload))

    def is_below_threshold(self, phase_name: str, result: SelfEvalResult) -> bool:
        if phase_name == "specification":
            return result.score < self.phase3_threshold
        if phase_name == "export":
            return result.score < self.phase5_threshold
        return False

    def _ensure_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            load_llm_keys_from_file()
            self._client = LLMFallbackClient.from_env()
            return self._client
        except Exception:
            return None

    def _call_llm(self, client: Any, system_prompt: str, user_prompt: str, *, default: SelfEvalResult) -> SelfEvalResult:
        try:
            data = client.chat_json(system_prompt, user_prompt)
        except Exception as exc:
            fallback = SelfEvalResult(score=default.score, issues=list(default.issues) + [f"LLM self-eval error: {exc}"], dimensions=default.dimensions, provider="fallback")
            return fallback

        score = max(0.0, min(1.0, float(data.get("score", default.score)))) if isinstance(data, dict) else default.score
        issues = [str(x) for x in data.get("issues", [])] if isinstance(data, dict) and isinstance(data.get("issues"), list) else list(default.issues)
        dims = data.get("dimensions") if isinstance(data, dict) and isinstance(data.get("dimensions"), dict) else dict(default.dimensions)
        provider = getattr(client, "last_provider", "llm") or "llm"
        return SelfEvalResult(score=score, issues=issues, dimensions=dims, provider=provider)

    def _deterministic_phase3(self, payload: dict[str, Any]) -> SelfEvalResult:
        dashboard = payload.get("dashboard_spec") if isinstance(payload.get("dashboard_spec"), dict) else {}
        pages = dashboard.get("pages") if isinstance(dashboard.get("pages"), list) else []
        visual_count = 0
        bound_visual_count = 0
        issues: list[str] = []

        for page in pages:
            page_d = page if isinstance(page, dict) else {}
            visuals = page_d.get("visuals") if isinstance(page_d.get("visuals"), list) else []
            visual_count += len(visuals)
            for visual in visuals:
                v = visual if isinstance(visual, dict) else {}
                binding = v.get("data_binding") if isinstance(v.get("data_binding"), dict) else {}
                axes = binding.get("axes") if isinstance(binding.get("axes"), dict) else {}
                if axes:
                    bound_visual_count += 1

        if visual_count == 0:
            issues.append("No visuals in abstract spec")
            score = 0.45
        else:
            coverage = bound_visual_count / max(1, visual_count)
            score = 0.6 + 0.4 * coverage
            if coverage < 0.7:
                issues.append("Low binding coverage in abstract spec")

        dims = {
            "structural_validity": score,
            "semantic_correctness": min(1.0, score + 0.05),
            "visual_coherence": score,
        }
        return SelfEvalResult(score=max(0.0, min(1.0, score)), issues=issues, dimensions=dims, provider="deterministic")

    def _deterministic_phase5(self, payload: dict[str, Any]) -> SelfEvalResult:
        validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
        content_bytes = int(payload.get("content_bytes") or 0)
        is_valid = bool(validation.get("is_valid", False))
        issues: list[str] = []

        if not is_valid:
            issues.append("RDL validation is not valid")
        if content_bytes <= 0:
            issues.append("RDL payload is empty")

        if is_valid and content_bytes > 0:
            score = 0.9
        elif content_bytes > 0:
            score = 0.6
        else:
            score = 0.3

        dims = {
            "structural_validity": 0.95 if is_valid else 0.5,
            "semantic_correctness": 0.8 if is_valid else 0.55,
            "visual_coherence": 0.8 if content_bytes > 0 else 0.4,
        }
        return SelfEvalResult(score=score, issues=issues, dimensions=dims, provider="deterministic")
