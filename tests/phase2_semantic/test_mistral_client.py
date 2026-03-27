from viz_agent.phase2_semantic.llm.mistral_client import call_mistral


def test_mistral_client_fallback_when_key_missing(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    resp = call_mistral("{\"column\": \"Amount\"}")
    assert resp.confidence == 0.0
    assert resp.error == "fallback"
