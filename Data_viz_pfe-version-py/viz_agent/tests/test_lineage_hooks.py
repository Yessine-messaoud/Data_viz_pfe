from __future__ import annotations

from viz_agent.phase1_parser.agent.lineage_hook import LineageHook as Phase1LineageHook
from viz_agent.phase2_semantic.agent.lineage_hook import LineageHook as Phase2LineageHook
from viz_agent.phase4_transform.agent.lineage_tracker import LineageTracker as Phase4LineageTracker


def test_phase1_lineage_hook_emits_event() -> None:
    events = Phase1LineageHook().capture({"dashboards": [], "visuals": []})
    assert events
    assert events[0]["phase"] == "phase1_parser"


def test_phase2_lineage_hook_emits_event() -> None:
    events = Phase2LineageHook().capture({"entities": [], "measures": []})
    assert events
    assert events[0]["phase"] == "phase2_semantic"


def test_phase4_lineage_tracker_emits_event() -> None:
    events = Phase4LineageTracker().capture({"datasets": [], "visuals": []})
    assert events
    assert events[0]["phase"] == "phase4_transform"


def test_lineage_hook_uses_external_agent() -> None:
    class FakeLineageAgent:
        def capture(self, _payload):
            return [{"phase": "external", "status": "ok"}]

    events = Phase1LineageHook(lineage_agent=FakeLineageAgent()).capture({"dashboards": []})
    phases = {item.get("phase") for item in events}
    assert "external" in phases
