"""
OutputSchema: Defines the semantic graph model for SemanticAgent
"""
from typing import Any, Dict, List

class OutputSchema:
    @staticmethod
    def example() -> Dict:
        return {
            "nodes": [
                {"id": "table_sales", "type": "Table", "name": "Sales"},
                {"id": "col_amount", "type": "Column", "name": "Amount", "table": "Sales"},
                {"id": "kpi_total_sales", "type": "KPI", "expression": "SUM(Amount)"},
                {"id": "dim_date", "type": "Dimension", "name": "Date"}
            ],
            "edges": [
                {"from": "table_sales", "to": "col_amount", "type": "has_column"},
                {"from": "col_amount", "to": "kpi_total_sales", "type": "used_in"},
                {"from": "dim_date", "to": "table_sales", "type": "join"}
            ],
            "confidence_score": 0.95,
            "validation_results": [],
            "lineage_events": [],
            "semantic_log": []
        }
