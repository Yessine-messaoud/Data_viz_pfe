from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass
class CachedPhaseRecord:
    phase: str
    fingerprint: str
    result: dict[str, Any]
    artifact_paths: dict[str, str]


class PhaseCacheStore:
    """Persistent file-based cache keyed by phase fingerprint."""

    CACHE_SCHEMA_VERSION = "v1"

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.phase_dir = cache_dir / "phases"
        self.artifact_dir = cache_dir / "artifacts"
        self.phase_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def compute_fingerprint(self, phase_name: str, payload: dict[str, Any]) -> str:
        body = {
            "schema": self.CACHE_SCHEMA_VERSION,
            "phase": phase_name,
            "payload": payload,
        }
        encoded = json.dumps(body, sort_keys=True, ensure_ascii=True, default=self._json_default).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, phase_name: str, fingerprint: str) -> CachedPhaseRecord | None:
        path = self._phase_file(phase_name, fingerprint)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(raw, dict):
            return None
        result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
        artifacts = raw.get("artifact_paths") if isinstance(raw.get("artifact_paths"), dict) else {}
        return CachedPhaseRecord(
            phase=phase_name,
            fingerprint=fingerprint,
            result=result,
            artifact_paths={str(k): str(v) for k, v in artifacts.items()},
        )

    def set(self, phase_name: str, fingerprint: str, result: dict[str, Any]) -> CachedPhaseRecord:
        artifact_paths = self._persist_selected_artifacts(phase_name, fingerprint, result)
        body = {
            "schema": self.CACHE_SCHEMA_VERSION,
            "phase": phase_name,
            "fingerprint": fingerprint,
            "result": result,
            "artifact_paths": artifact_paths,
        }
        path = self._phase_file(phase_name, fingerprint)
        path.write_text(json.dumps(body, indent=2, ensure_ascii=True, default=self._json_default), encoding="utf-8")
        return CachedPhaseRecord(phase=phase_name, fingerprint=fingerprint, result=result, artifact_paths=artifact_paths)

    def _persist_selected_artifacts(self, phase_name: str, fingerprint: str, result: dict[str, Any]) -> dict[str, str]:
        output = result.get("output") if isinstance(result.get("output"), dict) else {}
        stored: dict[str, str] = {}

        if phase_name == "data_extraction" and isinstance(output.get("metadata"), dict):
            stored["metadata"] = self._write_artifact(phase_name, fingerprint, "metadata", output["metadata"])

        if phase_name == "parsing" and isinstance(output.get("parsed_structure"), dict):
            stored["parsed_structure"] = self._write_artifact(phase_name, fingerprint, "parsed_structure", output["parsed_structure"])

        if phase_name == "specification" and isinstance(output.get("abstract_spec"), dict):
            stored["abstract_spec"] = self._write_artifact(phase_name, fingerprint, "abstract_spec", output["abstract_spec"])

        return stored

    def _write_artifact(self, phase_name: str, fingerprint: str, label: str, payload: dict[str, Any]) -> str:
        path = self.artifact_dir / f"{phase_name}_{fingerprint[:12]}_{label}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=self._json_default), encoding="utf-8")
        return str(path)

    def _phase_file(self, phase_name: str, fingerprint: str) -> Path:
        safe_phase = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in phase_name)
        return self.phase_dir / f"{safe_phase}_{fingerprint}.json"

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="json")
            return dumped
        return str(value)
