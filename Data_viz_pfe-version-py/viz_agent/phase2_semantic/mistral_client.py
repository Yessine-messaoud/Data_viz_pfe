from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib import error, request


@dataclass
class MistralConfig:
    api_key: str
    model: str = "mistral-small-latest"
    base_url: str = "https://api.mistral.ai/v1"
    timeout_seconds: int = 30


class MistralApiClient:
    def __init__(self, config: MistralConfig):
        self.config = config
        self.last_call_success: bool | None = None
        self.last_error: str = ""

    @classmethod
    def from_env(cls) -> "MistralApiClient":
        api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY is required for MistralApiClient")

        model = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip() or "mistral-small-latest"
        base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1").strip() or "https://api.mistral.ai/v1"
        return cls(MistralConfig(api_key=api_key, model=model, base_url=base_url))

    def _request(self, payload: dict) -> str:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.config.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
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
            raise RuntimeError(f"Mistral HTTP error {exc.code}: {details}") from exc
        except error.URLError as exc:
            self.last_call_success = False
            self.last_error = str(exc)
            raise RuntimeError(f"Mistral connection error: {exc}") from exc

        parsed = json.loads(body)
        return parsed.get("choices", [{}])[0].get("message", {}).get("content", "")

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        content = self._request(payload)

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Mistral returned non-JSON content: {content}") from exc

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        return self._request(payload).strip()
