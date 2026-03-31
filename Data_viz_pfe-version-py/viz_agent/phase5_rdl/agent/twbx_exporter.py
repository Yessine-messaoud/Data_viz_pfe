"""
TWBXExporter: Générateur et exporteur TWBX (Tableau)
"""
from typing import Any, Dict
from .twbx_generator import TWBXGenerator
from .twbx_validator import TWBXValidator

class TWBXExporter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.generator = TWBXGenerator(config.get("twbx", {}))
        self.validator = TWBXValidator()

    def export(self, model: Any, options: Dict[str, Any]) -> Dict:
        extract_data = options.get("extract_data")
        twbx_content = self.generator.generate(model, extract_data)
        validation = self.validator.validate(twbx_content)
        return {
            "content": twbx_content,
            "format": "twbx",
            "metadata": {"filename": f"{model.name}.twbx"},
            "validation": validation
        }
