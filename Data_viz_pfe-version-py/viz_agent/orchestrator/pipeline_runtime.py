from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def fingerprint_file(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_phase_fingerprint(base: str, phase: str, upstream_fingerprint: str = "") -> str:
    payload = f"base={base}|phase={phase}|upstream={upstream_fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def aggregate_confidence(phase_results: list[Any]) -> float:
    if not phase_results:
        return 0.0

    scored: list[float] = []
    for result in phase_results:
        if isinstance(result, dict):
            ok = bool(result.get("ok", False))
            confidence = float(result.get("confidence", 0.0) or 0.0)
        else:
            ok = bool(getattr(result, "ok", False))
            confidence = float(getattr(result, "confidence", 0.0) or 0.0)
        if not ok:
            scored.append(0.0)
        else:
            scored.append(max(0.0, min(1.0, confidence)))

    if not scored:
        return 0.0
    return round(sum(scored) / len(scored), 4)


class PipelinePhaseCache:
    def __init__(self, cache_dir: Path | None = None, ttl_seconds: int | None = None) -> None:
        self.cache_dir = cache_dir or Path(
            os.getenv("VIZ_AGENT_PIPELINE_CACHE_DIR", ".vizagent_cache/pipeline_phases")
        )
        self.ttl_seconds = int(
            ttl_seconds
            if ttl_seconds is not None
            else os.getenv("VIZ_AGENT_PIPELINE_CACHE_TTL_SECONDS", "21600")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, phase: str, fingerprint: str) -> Path:
        safe_phase = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in phase)
        return self.cache_dir / safe_phase / f"{fingerprint}.json"

    def get(self, phase: str, fingerprint: str) -> dict[str, Any] | None:
        path = self._cache_path(phase, fingerprint)
        if not path.exists():
            return None

        if self.ttl_seconds > 0:
            age_seconds = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
            if age_seconds > self.ttl_seconds:
                return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def set(self, phase: str, fingerprint: str, payload: dict[str, Any]) -> Path:
        path = self._cache_path(phase, fingerprint)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path


class PipelineTrace:
    def __init__(self, trace_path: Path) -> None:
        self.trace_path = trace_path
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, phase: str, status: str, details: dict[str, Any] | None = None) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "status": status,
            "details": details or {},
        }
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")
