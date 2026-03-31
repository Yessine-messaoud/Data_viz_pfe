"""
ExportAgent: Agentic refactor for Export phase (RDL, TWBX)
"""
from typing import Any, Dict, Optional, List
from .rdl_exporter import RDLExporter
from .twbx_exporter import TWBXExporter
from .validation_hook import ValidationHook
from .lineage_tracker import LineageTracker
from enum import Enum

class ExportFormat(Enum):
    RDL = "rdl"
    TWBX = "twbx"
    PBIX = "pbix"
    CSV = "csv"
    JSON = "json"

class ExportAgent:
    """
    Agent principal d'export coordonnant les différents exporteurs (RDL, TWBX, ...)
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validation_hook = ValidationHook()
        self.lineage_tracker = LineageTracker()
        self.exporters = {
            ExportFormat.RDL: RDLExporter(config),
            ExportFormat.TWBX: TWBXExporter(config),
        }
        # Extension: ajouter d'autres exporteurs si besoin

    def export(self, model: Any, target_format: ExportFormat, options: Optional[Dict[str, Any]] = None) -> Dict:
        options = options or {}
        if target_format not in self.exporters:
            raise ValueError(f"Format {target_format} not supported")
        exporter = self.exporters[target_format]
        # Validation pré-export
        self.validation_hook.pre_export(model, target_format)
        result = exporter.export(model, options)
        # Validation post-export
        result["validation"] = self.validation_hook.post_export(result["content"], target_format)
        # Lineage
        result["lineage"] = self.lineage_tracker.capture(model, target_format)
        return result
