"""Compatibility extraction agent for orchestrator wiring."""

from __future__ import annotations

from typing import Any, Dict

from viz_agent.phase0_extraction.pipeline import MetadataExtractor


class DataExtractionAgent:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}
        self.extractor = MetadataExtractor()

    def run(self, step: Dict[str, Any]) -> Dict[str, Any]:
        inputs = step.get("inputs", {})
        artifacts = inputs.get("artifacts", {})
        source_path = artifacts.get("source_path") or artifacts.get("input_path")
        if not source_path:
            return {"error": "missing source_path", "validation_status": "failed"}

        model = self.extractor.extract(source_path)
        return {
            "data": model.model_dump(mode="json"),
            "validation_status": "passed" if model.tables else "failed",
        }