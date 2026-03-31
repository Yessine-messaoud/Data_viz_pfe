"""
RDLExporter: Générateur et exporteur RDL (SSRS)
"""
from typing import Any, Dict
from .rdl_generator import RDLGenerator
from .rdl_validator import RDLValidator

class RDLExporter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.generator = RDLGenerator(config.get("rdl", {}))
        self.validator = RDLValidator()

    def export(self, model: Any, options: Dict[str, Any]) -> Dict:
        rdl_content = self.generator.generate(model)
        validation = self.validator.validate(rdl_content.encode("utf-8"))
        return {
            "content": rdl_content.encode("utf-8"),
            "format": "rdl",
            "metadata": {"filename": f"{model.name}.rdl"},
            "validation": validation
        }
