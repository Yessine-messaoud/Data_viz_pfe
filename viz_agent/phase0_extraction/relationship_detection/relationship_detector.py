from __future__ import annotations

from typing import Any

from viz_agent.phase0_extraction.models import Relationship, Table


def detect_from_fk(engine: Any) -> list[Relationship]:
    """Detect relationships from database foreign key metadata."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")


def detect_from_heuristics(tables: list[Table]) -> list[Relationship]:
    """Infer relationships with naming heuristics such as *ID and *Key."""
    raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")
