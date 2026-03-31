"""
RulesConfig: Charge et gère les règles de transformation (YAML/JSON)
"""
from typing import Any
import yaml
import json

class RulesConfig:
    def __init__(self, path: str = None):
        self.rules = {}
        if path:
            if path.endswith('.yaml') or path.endswith('.yml'):
                with open(path, 'r', encoding='utf-8') as f:
                    self.rules = yaml.safe_load(f)
            elif path.endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f:
                    self.rules = json.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        return self.rules.get(key, default)
