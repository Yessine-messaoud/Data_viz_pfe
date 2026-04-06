from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib import error, parse, request

from viz_agent.phase2_semantic.mistral_client import MistralApiClient, MistralConfig


def _parse_api_key_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines()]
    current_section = ""
    parsed: dict[str, str] = {}

    def _normalize_key(raw: str) -> str:
        lowered = re.sub(r"[^a-z0-9]+", "", raw.lower())
        if "mistral" in lowered:
            return "mistral"
        if "gemini" in lowered:
            return "gemini"
        return lowered

    for line in lines:
        if not line:
            continue
        if line.endswith(":"):
            current_section = _normalize_key(line[:-1].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            k = _normalize_key(key.strip())
            v = value.strip()
            if k and v:
                parsed[k] = v
            continue
        if current_section and current_section not in parsed:
            parsed[current_section] = line

    return parsed


def load_llm_keys_from_file() -> None:
    if os.getenv("MISTRAL_API_KEY", "").strip() and os.getenv("GEMINI_API_KEY", "").strip():
        return

    configured = os.getenv("VIZ_AGENT_API_KEY_FILE", "").strip()
    candidate_paths: list[Path] = []
    if configured:
        candidate_paths.append(Path(configured))
    else:
        cwd = Path.cwd()
        candidate_paths.extend(
            [
                cwd / "API_KEY.txt",
                cwd.parent / "API_KEY.txt",
                cwd.parent.parent / "API_KEY.txt",
            ]
        )

    for path in candidate_paths:
        parsed = _parse_api_key_file(path)
        mistral_key = parsed.get("mistral", "")
        gemini_key = parsed.get("gemini", "")
        if mistral_key and not os.getenv("MISTRAL_API_KEY", "").strip():
            os.environ["MISTRAL_API_KEY"] = mistral_key
        if gemini_key and not os.getenv("GEMINI_API_KEY", "").strip():
            os.environ["GEMINI_API_KEY"] = gemini_key
        if os.getenv("MISTRAL_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip():
            return


@dataclass
class GeminiConfig:
    api_key: str
    model: str = "gemini-2.0-flash"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    timeout_seconds: int = 20


class GeminiApiClient:
    def __init__(self, config: GeminiConfig):
        self.config = config
        self.last_call_success: bool | None = None
        self.last_error: str = ""

    @classmethod
    def from_env(cls) -> "GeminiApiClient":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for GeminiApiClient")
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
        base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip()
        timeout = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
        return cls(GeminiConfig(api_key=api_key, model=model, base_url=base_url, timeout_seconds=timeout))

    def _request_with_model(self, model_name: str, payload: dict) -> str:
        query = parse.urlencode({"key": self.config.api_key})
        url = f"{self.config.base_url}/models/{model_name}:generateContent?{query}"
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                self.last_call_success = True
                self.last_error = ""
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            self.last_call_success = False
            self.last_error = f"HTTP {exc.code}: {details}"
            raise RuntimeError(f"Gemini HTTP error {exc.code}: {details}") from exc
        except Exception as exc:
            self.last_call_success = False
            self.last_error = str(exc)
            raise RuntimeError(f"Gemini connection error: {exc}") from exc

        parsed_body = json.loads(body)
        candidates = parsed_body.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise RuntimeError("Gemini returned empty content")
        return text

    def _request(self, payload: dict) -> str:
        candidates = [self.config.model]
        env_candidates = os.getenv(
            "GEMINI_MODEL_CANDIDATES",
            "gemini-2.0-flash,gemini-1.5-flash-latest,gemini-1.5-pro",
        )
        for name in [item.strip() for item in env_candidates.split(",") if item.strip()]:
            if name not in candidates:
                candidates.append(name)

        last_error = ""
        for model_name in candidates:
            try:
                return self._request_with_model(model_name, payload)
            except RuntimeError as exc:
                text = str(exc)
                last_error = text
                if "HTTP error 404" not in text and "NOT_FOUND" not in text:
                    raise
                continue

        raise RuntimeError(last_error or "Gemini request failed")

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
            },
        }
        return self._request(payload).strip()

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        content = self._request(payload).strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)


@dataclass
class OllamaConfig:
    model: str = "mistral"
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: int = 30


class OllamaApiClient:
    def __init__(self, config: OllamaConfig):
        self.config = config
        self.last_call_success: bool | None = None
        self.last_error: str = ""

    @classmethod
    def from_env(cls) -> "OllamaApiClient":
        model = os.getenv("OLLAMA_MODEL", "mistral").strip() or "mistral"
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip() or "http://127.0.0.1:11434"
        timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
        return cls(OllamaConfig(model=model, base_url=base_url, timeout_seconds=timeout))

    def _request(self, prompt: str, expect_json: bool) -> str:
        url = f"{self.config.base_url}/api/generate"
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
        req = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                self.last_call_success = True
                self.last_error = ""
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            self.last_call_success = False
            self.last_error = f"HTTP {exc.code}: {details}"
            raise RuntimeError(f"Ollama HTTP error {exc.code}: {details}") from exc
        except Exception as exc:
            self.last_call_success = False
            self.last_error = str(exc)
            raise RuntimeError(f"Ollama connection error: {exc}") from exc

        parsed = json.loads(body)
        text = str(parsed.get("response", "")).strip()
        if not text:
            raise RuntimeError("Ollama returned empty response")
        if expect_json and text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return text

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}\n\nASSISTANT:"
        return self._request(prompt, expect_json=False).strip()

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        prompt = (
            f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}\n\n"
            "IMPORTANT: Return only valid JSON object. No markdown.\n\nASSISTANT:"
        )
        content = self._request(prompt, expect_json=True).strip()
        return json.loads(content)


class LLMFallbackClient:
    """Try Mistral API, then Gemini API, then local Ollama on timeout/failure."""

    def __init__(
        self,
        mistral_client: MistralApiClient | None,
        gemini_client: GeminiApiClient | None,
        ollama_client: OllamaApiClient | None,
    ):
        self.mistral = mistral_client
        self.gemini = gemini_client
        self.ollama = ollama_client
        self.last_provider: str = ""
        self.last_attempted_provider: str = ""
        self.last_error: str = ""

    @classmethod
    def from_env(cls) -> "LLMFallbackClient":
        load_llm_keys_from_file()

        mistral_key = os.getenv("MISTRAL_API_KEY", "").strip()
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        mistral_client = None
        if mistral_key:
            mistral_timeout = int(os.getenv("MISTRAL_TIMEOUT_SECONDS", "15"))
            mistral_model = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip() or "mistral-small-latest"
            mistral_base = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1").strip()
            mistral_client = MistralApiClient(
                MistralConfig(
                    api_key=mistral_key,
                    model=mistral_model,
                    base_url=mistral_base,
                    timeout_seconds=mistral_timeout,
                )
            )

        gemini_client = None
        if gemini_key:
            gemini_client = GeminiApiClient.from_env()

        ollama_enabled = os.getenv("OLLAMA_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
        ollama_client = OllamaApiClient.from_env() if ollama_enabled else None

        if mistral_client is None and gemini_client is None and ollama_client is None:
            raise RuntimeError("No LLM provider available (MISTRAL_API_KEY, GEMINI_API_KEY or OLLAMA_ENABLED)")
        return cls(mistral_client, gemini_client, ollama_client)

    def _call(self, method: str, system_prompt: str, user_prompt: str):
        errors: list[str] = []

        if self.mistral is not None:
            try:
                self.last_attempted_provider = "mistral"
                result = getattr(self.mistral, method)(system_prompt, user_prompt)
                self.last_provider = "mistral"
                self.last_error = ""
                return result
            except Exception as exc:
                errors.append(f"mistral: {exc}")

        if self.gemini is not None:
            try:
                self.last_attempted_provider = "gemini"
                result = getattr(self.gemini, method)(system_prompt, user_prompt)
                self.last_provider = "gemini"
                self.last_error = ""
                return result
            except Exception as exc:
                errors.append(f"gemini: {exc}")

        if self.ollama is not None:
            try:
                self.last_attempted_provider = "ollama"
                result = getattr(self.ollama, method)(system_prompt, user_prompt)
                self.last_provider = "ollama"
                self.last_error = ""
                return result
            except Exception as exc:
                errors.append(f"ollama: {exc}")

        self.last_error = " | ".join(errors)
        raise RuntimeError(f"All LLM providers failed: {self.last_error}")

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        return str(self._call("chat_text", system_prompt, user_prompt)).strip()

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        result = self._call("chat_json", system_prompt, user_prompt)
        if not isinstance(result, dict):
            raise RuntimeError("LLM JSON response is not an object")
        return result
