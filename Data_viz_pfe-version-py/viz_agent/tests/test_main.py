from __future__ import annotations

import os
from pathlib import Path

import pytest

from viz_agent.main import _detect_intent_type, _ensure_mistral_api_key


def test_ensure_mistral_api_key_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "abc123")
    assert _ensure_mistral_api_key() == "abc123"


def test_ensure_mistral_api_key_fails_if_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "")

    with pytest.raises(RuntimeError, match="Mistral API key is required"):
        _ensure_mistral_api_key()


def test_detect_intent_type_for_tableau_conversion() -> None:
    intent = _detect_intent_type(Path("input/workbook.twb"), Path("output/report.rdl"))
    assert intent == "conversion"
