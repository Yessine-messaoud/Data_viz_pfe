from __future__ import annotations

from viz_agent.phase0_extraction.models import Column, MetadataModel, Table


class MetadataCatalog:
    """Query helper around MetadataModel for UI and pipeline consumers."""

    def __init__(self, model: MetadataModel):
        self._model = model

    def get_tables(self, used_only: bool = False) -> list[Table]:
        if not used_only:
            return list(self._model.tables)
        return [table for table in self._model.tables if table.is_used_in_dashboard]

    def get_columns(self, table_name: str, used_only: bool = False) -> list[Column]:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")

    def search(self, keyword: str) -> list[Column]:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")

    def get_available_for_dragdrop(self) -> list[Column]:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")

    def to_json(self, path: str) -> None:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")

    def to_yaml(self, path: str) -> None:
        raise NotImplementedError("Sprint 1 scaffold: implement in Sprint 3")
