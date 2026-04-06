"""Strict mapping layer: Tableau → Abstract Spec → RDL"""
from __future__ import annotations
from typing import Literal

# Tableau Mark Type to Logical Type mapping
TABLEAU_TO_LOGICAL = {
    "Bar": "bar",
    "Line": "line",
    "Circle": "scatter",
    "Square": "treemap",
    "Treemap": "treemap",
    "Pie": "pie",
    "Map": "map",
    "Text": "table",
    "Gantt": "gantt",
}

# Logical Type to RDL-specific rendering type
LOGICAL_TO_RDL = {
    "bar": "ColumnChart",
    "line": "LineChart",
    "pie": "PieChart",
    "treemap": "TreeMap",
    "scatter": "ScatterChart",
    "table": "Tablix",
    "kpi": "Textbox",
    "map": "Map",
    "gantt": "Tablix",
}

# RDL type to chart subtype (for Chart element specification)
RDL_CHART_SUBTYPES = {
    "ColumnChart": "Column",
    "BarChart": "Bar",
    "LineChart": "Line",
    "PieChart": "Pie",
    "ScatterChart": "Scatter",
    "AreaChart": "Area",
}


class VisualizationMapper:
    """Strict bidirectional mapper for visualization types"""
    
    @staticmethod
    def tableau_to_logical(mark_type: str, worksheet_name: str = "") -> str:
        """Convert Tableau mark type to logical visualization type"""
        if mark_type in TABLEAU_TO_LOGICAL:
            return TABLEAU_TO_LOGICAL[mark_type]
        
        # Heuristic fallback based on worksheet name
        lower_name = worksheet_name.lower()
        if "kpi" in lower_name:
            return "kpi"
        if any(kw in lower_name for kw in ("map", "country", "geo", "region")):
            return "map"
        if any(kw in lower_name for kw in ("trend", "evolution", "time", "month", "year")):
            return "line"
        
        return "table"
    
    @staticmethod
    def logical_to_rdl(logical_type: str) -> str:
        """Convert logical type to RDL rendering type"""
        if logical_type not in LOGICAL_TO_RDL:
            raise ValueError(
                f"Unknown logical type: {logical_type}. "
                f"Allowed: {', '.join(LOGICAL_TO_RDL.keys())}"
            )
        return LOGICAL_TO_RDL[logical_type]
    
    @staticmethod
    def rdl_to_chart_subtype(rdl_type: str) -> str:
        """Get the Chart element subtype (Column, Pie, Line, etc.)"""
        if rdl_type in RDL_CHART_SUBTYPES:
            return RDL_CHART_SUBTYPES[rdl_type]
        raise ValueError(
            f"RDL type {rdl_type} does not map to a Chart subtype. "
            f"Chart types: {', '.join(RDL_CHART_SUBTYPES.keys())}"
        )
    
    @staticmethod
    def tableau_to_rdl(mark_type: str, worksheet_name: str = "") -> str:
        """Direct conversion: Tableau mark type → RDL type"""
        logical = VisualizationMapper.tableau_to_logical(mark_type, worksheet_name)
        return VisualizationMapper.logical_to_rdl(logical)
    
    @staticmethod
    def full_chain(mark_type: str, worksheet_name: str = "") -> dict[str, str]:
        """Get full mapping chain"""
        logical = VisualizationMapper.tableau_to_logical(mark_type, worksheet_name)
        rdl = VisualizationMapper.logical_to_rdl(logical)
        
        # Determine chart_type based on RDL type
        chart_type = None
        if rdl in RDL_CHART_SUBTYPES:
            chart_type = RDL_CHART_SUBTYPES[rdl]
        
        return {
            "tableau_mark": mark_type,
            "logical_type": logical,
            "rdl_type": rdl,
            "chart_type": chart_type,
        }


class EncodingRequirements:
    """Defines required encoding axes for each visualization type"""
    
    REQUIREMENTS = {
        "bar": {"required": ["x", "y"], "optional": ["color", "size"]},
        "line": {"required": ["x", "y"], "optional": ["color"]},
        "pie": {"required": ["y"], "optional": ["color", "details"]},
        "treemap": {"required": ["size"], "optional": ["color", "details"]},
        "scatter": {"required": ["x", "y"], "optional": ["color", "size"]},
        "table": {"required": [], "optional": ["all"]},
        "kpi": {"required": [], "optional": ["y"]},
        "map": {"required": [], "optional": ["all"]},
        "gantt": {"required": ["x", "y"], "optional": ["color"]},
    }
    
    @staticmethod
    def validate_encoding(visual_type: str, encoding: dict) -> tuple[bool, list[str]]:
        """Validate encoding against requirements"""
        if visual_type not in EncodingRequirements.REQUIREMENTS:
            return False, [f"Unknown visualization type: {visual_type}"]
        
        req = EncodingRequirements.REQUIREMENTS[visual_type]
        missing = []
        
        for required_axis in req["required"]:
            if not encoding.get(required_axis):
                missing.append(f"Missing required encoding axis '{required_axis}' for {visual_type}")
        
        return len(missing) == 0, missing
