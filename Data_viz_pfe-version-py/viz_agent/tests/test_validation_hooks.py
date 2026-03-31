from __future__ import annotations

from viz_agent.phase1_parser.agent.validation_hook import ValidationHook as Phase1ValidationHook
from viz_agent.phase2_semantic.agent.validation_hook import ValidationHook as Phase2ValidationHook
from viz_agent.phase4_transform.agent.validation_hook import ValidationHook as Phase4ValidationHook


def test_phase1_validation_hook_flags_missing_dashboards() -> None:
    issues = Phase1ValidationHook().validate({"visuals": []})
    codes = {item.get("code") for item in issues}
    assert "P1_V002" in codes


def test_phase2_validation_hook_flags_empty_graph() -> None:
    issues = Phase2ValidationHook().validate({})
    codes = {item.get("code") for item in issues}
    assert "P2_V002" in codes


def test_phase4_validation_hook_flags_error_key() -> None:
    issues = Phase4ValidationHook().validate({"error": "boom"})
    codes = {item.get("code") for item in issues}
    assert "P4_V002" in codes


def test_validation_hook_uses_external_agent() -> None:
    class FakeValidator:
        def validate(self, _payload):
            return [{"severity": "warning", "code": "EXT_001", "message": "external"}]

    issues = Phase1ValidationHook(validation_agent=FakeValidator()).validate({"dashboards": []})
    codes = {item.get("code") for item in issues}
    assert "EXT_001" in codes
