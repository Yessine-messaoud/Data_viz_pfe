from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def _safe_name(value: Any) -> str:
    return str(value or "").strip()


def stable_semantic_cache_key(workbook: Any) -> str:
    datasources = []
    for ds in getattr(workbook, "datasources", []) or []:
        cols = []
        for col in getattr(ds, "columns", []) or []:
            cols.append(
                {
                    "name": _safe_name(getattr(col, "name", "")),
                    "role": _safe_name(getattr(col, "role", "unknown")),
                    "type": _safe_name(getattr(col, "pbi_type", "text")),
                }
            )
        cols.sort(key=lambda item: (item["name"].lower(), item["role"], item["type"]))
        datasources.append(
            {
                "name": _safe_name(getattr(ds, "name", "")),
                "caption": _safe_name(getattr(ds, "caption", "")),
                "columns": cols,
            }
        )

    datasources.sort(key=lambda item: (item["name"].lower(), item["caption"].lower()))

    worksheet_marks = []
    for ws in getattr(workbook, "worksheets", []) or []:
        worksheet_marks.append(
            {
                "worksheet": _safe_name(getattr(ws, "name", "")),
                "mark_type": _safe_name(getattr(ws, "mark_type", "")).lower(),
                "datasource": _safe_name(getattr(ws, "datasource_name", "")),
            }
        )

    worksheet_marks.sort(key=lambda item: (item["worksheet"].lower(), item["mark_type"], item["datasource"].lower()))

    payload = {
        "datasources": datasources,
        "worksheet_marks": worksheet_marks,
    }
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class SemanticCache:
    def __init__(self, cache_dir: str | Path, ttl_seconds: int = 21600) -> None:
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = int(ttl_seconds)

    def _cache_file(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get_cache(self, key: str) -> dict[str, Any] | None:
        try:
            path = self._cache_file(key)
            if not path.exists():
                return None
            if self.ttl_seconds > 0:
                age = time.time() - path.stat().st_mtime
                if age > self.ttl_seconds:
                    return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set_cache(self, key: str, value: dict[str, Any]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_file(key).write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding="utf-8")
        except Exception:
            return
