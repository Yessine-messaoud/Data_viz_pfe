from __future__ import annotations

import re


class LogicalNameRegistry:
    """Keeps a deterministic physical->logical table name mapping."""

    def __init__(self) -> None:
        self._mapping: dict[str, str] = {}
        self._reverse_used: set[str] = set()

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)

    def register(self, physical_name: str, logical_name: str) -> str:
        physical = str(physical_name or "").strip()
        candidate = self._normalize(logical_name)
        if not candidate:
            candidate = self._normalize(physical)
        if not candidate:
            candidate = "table"

        unique = self._ensure_unique(candidate)
        self._mapping[physical] = unique
        return unique

    def resolve(self, physical_name: str, caption: str = "") -> str:
        physical = str(physical_name or "").strip()
        if physical in self._mapping:
            return self._mapping[physical]

        preferred = self._preferred_logical_name(physical, caption)
        return self.register(physical, preferred)

    def _preferred_logical_name(self, physical_name: str, caption: str) -> str:
        physical = str(physical_name or "").strip()
        caption_clean = self._normalize(caption)

        if caption_clean and self._looks_technical(physical):
            return caption_clean
        if caption_clean and not self._looks_technical(caption):
            return caption_clean
        if not self._looks_technical(physical):
            return self._normalize(physical)
        return caption_clean or self._normalize(physical)

    def _looks_technical(self, name: str) -> bool:
        text = str(name or "").strip().lower()
        if text.startswith("federated."):
            return True
        if re.search(r"[0-9]{8,}", text):
            return True
        if re.fullmatch(r"[a-f0-9]{16,}", text):
            return True
        return False

    def _normalize(self, raw: str) -> str:
        text = str(raw or "").strip()
        text = text.strip("[]\"'`")
        text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        if not text:
            return ""
        if re.match(r"^[0-9]", text):
            text = f"table_{text}"
        return text[:120]

    def _ensure_unique(self, base: str) -> str:
        lower = base.lower()
        if lower not in self._reverse_used:
            self._reverse_used.add(lower)
            return base

        idx = 2
        candidate = f"{base}_{idx}"
        while candidate.lower() in self._reverse_used:
            idx += 1
            candidate = f"{base}_{idx}"
        self._reverse_used.add(candidate.lower())
        return candidate
