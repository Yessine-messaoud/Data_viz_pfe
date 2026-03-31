"""
OutputSchema: Defines the tool-specific model for TransformationAgent
"""
from typing import Any, Dict

class OutputSchema:
    @staticmethod
    def example_powerbi() -> Dict:
        return {
            "powerbi_model": {
                "data_model": {
                    "tables": [
                        {
                            "name": "Sales",
                            "columns": [
                                {"name": "Amount", "dataType": "decimal", "isHidden": False, "summarizeBy": "sum"}
                            ],
                            "measures": [
                                {"name": "Total Sales", "expression": "SUM(Sales[Amount])", "formatString": "$#,##0.00", "isHidden": False}
                            ],
                            "relationships": []
                        }
                    ]
                },
                "visualizations": [
                    {
                        "visualType": "lineChart",
                        "dataMapping": {"fields": ["Amount"], "aggregations": ["sum"]},
                        "formatting": {},
                        "position": {}
                    }
                ],
                "pages": [],
                "parameters": [],
                "filters": []
            }
        }
    @staticmethod
    def example_tableau() -> Dict:
        return {
            "tableau_model": {
                "data_sources": [
                    {
                        "name": "Sales",
                        "connection": {"type": "extract", "tables": ["Sales"]},
                        "fields": [
                            {"name": "Amount", "role": "measure", "dataType": "float", "aggregation": "sum", "defaultFormat": {}}
                        ],
                        "calculated_fields": [
                            {"name": "Total Sales", "formula": "SUM([Amount])", "dataType": "float"}
                        ]
                    }
                ],
                "worksheets": [
                    {
                        "name": "Sales Trend",
                        "markType": "line",
                        "columns": ["Date"],
                        "rows": ["Amount"],
                        "color": {},
                        "size": {},
                        "filters": []
                    }
                ],
                "dashboards": []
            }
        }
