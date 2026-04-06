from __future__ import annotations

import json
from pathlib import Path

from viz_agent.orchestrator.pipeline_runtime import (
    PipelinePhaseCache,
    PipelineTrace,
    aggregate_confidence,
    build_phase_fingerprint,
)


def test_build_phase_fingerprint_changes_with_upstream() -> None:
    fp1 = build_phase_fingerprint("base", "phase2", "upstream_a")
    fp2 = build_phase_fingerprint("base", "phase2", "upstream_b")
    assert fp1 != fp2


def test_aggregate_confidence_uses_ok_and_confidence() -> None:
    results = [
        {"ok": True, "confidence": 1.0},
        {"ok": True, "confidence": 0.5},
        {"ok": False, "confidence": 0.9},
    ]
    assert aggregate_confidence(results) == 0.5


def test_pipeline_phase_cache_roundtrip(tmp_path: Path) -> None:
    cache = PipelinePhaseCache(cache_dir=tmp_path / "cache", ttl_seconds=3600)
    payload = {"a": 1, "b": "ok"}
    cache.set("phaseX", "abc", payload)
    loaded = cache.get("phaseX", "abc")
    assert loaded == payload


def test_pipeline_trace_writes_jsonl(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    trace = PipelineTrace(trace_path)
    trace.emit("phase1", "start", {"step": 1})
    trace.emit("phase1", "ok", {"step": 1})

    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["phase"] == "phase1"
    assert first["status"] == "start"
