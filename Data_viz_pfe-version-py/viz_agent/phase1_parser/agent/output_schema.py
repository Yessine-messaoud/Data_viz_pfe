"""
OutputSchema: Defines the universal parsing model for ParsingAgent
"""
from typing import Any, Dict, List

class OutputSchema:
    @staticmethod
    def example() -> Dict:
        return {
            "dashboards": [
                {
                    "name": "...",
                    "pages": [
                        {"name": "...", "visuals": ["..."], "layout": {"position": "...", "size": "..."}},
                    ],
                    "visuals": [
                        {
                            "id": "...",
                            "type": "BAR|LINE|PIE|TABLE|KPI|...",
                            "fields": ["..."],
                            "filters": ["..."],
                            "measures": ["..."],
                            "bindings": {"x": "...", "y": "..."},
                            "interactions": {"drill_down": ["..."], "cross_filter": ["..."]}
                        }
                    ],
                    "filters": [
                        {"id": "...", "scope": "GLOBAL|PAGE|VISUAL", "condition": {"field": "...", "operator": "...", "value": "..."}}
                    ]
                }
            ]
        }
