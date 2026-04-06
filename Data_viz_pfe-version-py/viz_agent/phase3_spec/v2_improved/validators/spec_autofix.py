"""Auto-fix layer for correcting broken specs"""
from __future__ import annotations
from typing import Any, Union
from viz_agent.phase3_spec.v2_improved.mappers.visualization_mapper import VisualizationMapper, RDL_CHART_SUBTYPES


class SpecAutoFixer:
    """Automatically fixes common specification issues"""
    
    @staticmethod
    def fix_generic_chart_type(visual_dict: dict, tableau_mark: str = "", worksheet_name: str = "") -> dict:
        """Replace generic 'chart' type with specific type inferred from Tableau mark"""
        # Handle nested structure with 'visualization' object
        needs_fix = False
        if visual_dict.get("visualization", {}).get("type") == "chart":
            needs_fix = True
        elif visual_dict.get("type") == "chart":
            needs_fix = True
        
        if not needs_fix:
            return visual_dict
        
        # Infer from tableau mark if available
        if tableau_mark:
            logical_type = VisualizationMapper.tableau_to_logical(tableau_mark, worksheet_name)
            rdl_type = VisualizationMapper.logical_to_rdl(logical_type)
        else:
            # Fallback: try to infer from other fields
            logical_type = SpecAutoFixer._infer_type_from_encoding(visual_dict)
            rdl_type = VisualizationMapper.logical_to_rdl(logical_type)
        
        # Update nested structure if present
        if "visualization" in visual_dict and isinstance(visual_dict["visualization"], dict):
            visual_dict["visualization"]["type"] = logical_type
        else:
            visual_dict["type"] = logical_type
        
        # Update RDL type
        if "rendering" in visual_dict and isinstance(visual_dict["rendering"], dict):
            visual_dict["rendering"]["rdl_type"] = rdl_type
        else:
            visual_dict["rdl_type"] = rdl_type
        
        return visual_dict
    
    @staticmethod
    def _infer_type_from_encoding(visual_dict: dict) -> str:
        """Infer visualization type from encoding fields"""
        # Handle nested structure
        if "encoding" in visual_dict and isinstance(visual_dict["encoding"], dict):
            encoding = visual_dict["encoding"]
        else:
            encoding = {}
            
        x = encoding.get("x")
        y = encoding.get("y")
        size = encoding.get("size")
        
        # Heuristics
        if size and not x and not y:
            return "treemap"
        if x and y:
            return "bar"  # Default to bar if both axes present
        if y and not x:
            return "pie"
        if x and not y:
            return "line"
        
        return "table"  # Safe default
    
    @staticmethod
    def fix_missing_encoding_axes(visual_dict: dict) -> dict:
        """Add missing default encoding axes"""
        # Get visualization type from either structure
        if "visualization" in visual_dict and isinstance(visual_dict["visualization"], dict):
            vis_type = visual_dict["visualization"].get("type", "table")
        else:
            vis_type = visual_dict.get("type", "table")
        
        # Get encoding
        if "encoding" in visual_dict and isinstance(visual_dict.get("encoding"), dict):
            encoding = visual_dict["encoding"]
        else:
            encoding = {}
        
        # For pie charts, ensure Y axis exists
        if vis_type == "pie":
            if not encoding.get("y"):
                # Find a numeric field from data binding
                if "data_binding" in visual_dict and isinstance(visual_dict["data_binding"], dict):
                    measures = visual_dict["data_binding"].get("measures", [])
                    if measures:
                        first_measure = measures[0] if isinstance(measures, list) else measures
                        encoding["y"] = {
                            "field": first_measure.get("name", "Measure") if isinstance(first_measure, dict) else first_measure,
                            "aggregation": "SUM",
                            "role": "measure"
                        }
        
        # For bar/line, ensure X and Y exist
        if vis_type in ["bar", "line"]:
            if not encoding.get("x"):
                encoding["x"] = {"field": "Dimension", "aggregation": "NONE", "role": "dimension"}
            if not encoding.get("y"):
                encoding["y"] = {"field": "Measure", "aggregation": "SUM", "role": "measure"}
        
        visual_dict["encoding"] = encoding
        return visual_dict
    
    @staticmethod
    def fix_rdl_type_mismatch(visual_dict: dict) -> dict:
        """Correct RDL type to match visualization type"""
        # Get visualization type from either structure
        if "visualization" in visual_dict and isinstance(visual_dict["visualization"], dict):
            vis_type = visual_dict["visualization"].get("type", "table")
            current_rdl = visual_dict.get("rendering", {}).get("rdl_type", "Tablix") if isinstance(visual_dict.get("rendering"), dict) else visual_dict.get("rdl_type", "Tablix")
        else:
            vis_type = visual_dict.get("type", "table")
            current_rdl = visual_dict.get("rdl_type", "Tablix")
        
        mapping = {
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
        
        expected_rdl = mapping.get(vis_type, "Tablix")
        
        if current_rdl != expected_rdl:
            # Update nested structure if present
            if "rendering" in visual_dict and isinstance(visual_dict["rendering"], dict):
                visual_dict["rendering"]["rdl_type"] = expected_rdl
                
                # Set chart subtype for Chart-based RDL types
                if expected_rdl.endswith("Chart"):
                    chart_subtype = RDL_CHART_SUBTYPES.get(expected_rdl)
                    if chart_subtype:
                        visual_dict["rendering"]["chart_type"] = chart_subtype
            else:
                visual_dict["rdl_type"] = expected_rdl
        
        return visual_dict
    
    @staticmethod
    def fix_missing_fact_table(visual_dict: dict, default_table: str = "fact_data") -> dict:
        """Add missing fact table reference"""
        data = visual_dict.get("data", {})
        if not data.get("fact_table"):
            if not isinstance(data, dict):
                data = {}
            data["fact_table"] = default_table
            visual_dict["data"] = data
        
        return visual_dict
    
    @staticmethod
    def autofix_visual(visual_dict: dict, tableau_mark: str = "") -> tuple[dict, list[str]]:
        """Apply all auto-fixes and return fixed dict + list of changes"""
        changes = []
        
        # Fix 1: Generic chart types
        before_type = visual_dict.get("visualization", {}).get("type") if isinstance(visual_dict.get("visualization"), dict) else visual_dict.get("type")
        before_rdl = visual_dict.get("rendering", {}).get("rdl_type") if isinstance(visual_dict.get("rendering"), dict) else visual_dict.get("rdl_type")
        
        if before_type == "chart" or before_rdl == "chart":
            visual_dict = SpecAutoFixer.fix_generic_chart_type(visual_dict, tableau_mark)
            after_type = visual_dict.get("visualization", {}).get("type") if isinstance(visual_dict.get("visualization"), dict) else visual_dict.get("type")
            if before_type == "chart" and after_type != "chart":
                changes.append(f"Fixed generic 'chart' type to '{after_type}'")
        
        # Fix 2: RDL type mismatch
        before_rdl = visual_dict.get("rendering", {}).get("rdl_type") if isinstance(visual_dict.get("rendering"), dict) else visual_dict.get("rdl_type")
        visual_dict = SpecAutoFixer.fix_rdl_type_mismatch(visual_dict)
        after_rdl = visual_dict.get("rendering", {}).get("rdl_type") if isinstance(visual_dict.get("rendering"), dict) else visual_dict.get("rdl_type")
        if before_rdl != after_rdl:
            changes.append(f"Fixed RDL type mismatch: {before_rdl} → {after_rdl}")
        
        # Fix 3: Missing encoding
        before_encoding = str(visual_dict.get("encoding"))
        visual_dict = SpecAutoFixer.fix_missing_encoding_axes(visual_dict)
        if before_encoding != str(visual_dict.get("encoding")):
            changes.append("Added missing encoding axes")
        
        # Fix 4: Missing fact table
        before_table = visual_dict.get("data", {}).get("fact_table") if isinstance(visual_dict.get("data"), dict) else None
        visual_dict = SpecAutoFixer.fix_missing_fact_table(visual_dict)
        after_table = visual_dict.get("data", {}).get("fact_table") if isinstance(visual_dict.get("data"), dict) else None
        if before_table != after_table and after_table:
            changes.append(f"Added missing fact_table: {after_table}")
        
        return visual_dict, changes
    
    @staticmethod
    def autofix_dashboard(dashboard_spec: dict) -> tuple[dict, dict]:
        """Apply auto-fixes to entire dashboard and return fixed spec + detailed report"""
        report = {
            "total_visuals": 0,
            "fixed_visuals": 0,
            "changes_per_visual": {}
        }
        
        pages = dashboard_spec.get("pages", [])
        for page_idx, page in enumerate(pages):
            visuals = page.get("visuals", [])
            for vis_idx, visual in enumerate(visuals):
                report["total_visuals"] += 1
                visual_id = visual.get("id", f"visual_{page_idx}_{vis_idx}")
                
                fixed_visual, changes = SpecAutoFixer.autofix_visual(visual)
                
                if changes:
                    report["fixed_visuals"] += 1
                    report["changes_per_visual"][visual_id] = changes
                
                page["visuals"][vis_idx] = fixed_visual
        
        return dashboard_spec, report
