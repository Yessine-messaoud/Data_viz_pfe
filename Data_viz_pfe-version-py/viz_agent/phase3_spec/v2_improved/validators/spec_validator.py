"""Strict validation for enhanced abstract specs"""
from __future__ import annotations
from typing import Any
from viz_agent.phase3_spec.v2_improved.models.visualization_model import VisualSpecV2, VisualizationType
from viz_agent.phase3_spec.v2_improved.mappers.visualization_mapper import EncodingRequirements


class ValidationIssue:
    """Represents a validation issue"""
    
    def __init__(self, code: str, severity: str, message: str, fix: str = ""):
        self.code = code
        self.severity = severity
        self.message = message
        self.fix = fix
    
    def __repr__(self):
        return f"{self.severity.upper()}[{self.code}]: {self.message} | Fix: {self.fix}"


class VisualSpecV2Validator:
    """Strict validator for enhanced visual specifications"""
    
    def validate_single_visual(self, visual: VisualSpecV2) -> tuple[bool, list[ValidationIssue]]:
        """Validate a single visual specification"""
        issues = []
        
        # Check 1: Visualization type must not be generic "chart"
        if visual.visualization.type == "chart":
            issues.append(ValidationIssue(
                code="VIS_GENERIC",
                severity="error",
                message=f"Visual '{visual.id}' has generic type 'chart', must use specific type",
                fix="Use one of: bar, line, pie, treemap, scatter, table, kpi, map, gantt"
            ))
        
        # Check 2: RDL type must not be generic "chart"
        if visual.rendering.rdl_type == "Chart":
            issues.append(ValidationIssue(
                code="RDL_GENERIC",
                severity="error",
                message=f"Visual '{visual.id}' has generic RDL type 'Chart'",
                fix=f"Use specific RDL type matching visualization type"
            ))
        
        # Check 3: RDL type must match visualization type
        valid_mapping, errors = self._validate_mapping(visual.visualization.type, visual.rendering.rdl_type)
        if not valid_mapping:
            for error_msg in errors:
                issues.append(ValidationIssue(
                    code="VIS_RDL_MISMATCH",
                    severity="error",
                    message=f"Visual '{visual.id}': {error_msg}",
                    fix="Ensure RDL type corresponds to visualization type"
                ))
        
        # Check 4: Validate required encoding axes
        encoding_dict = {
            "x": visual.encoding.x,
            "y": visual.encoding.y,
            "color": visual.encoding.color,
            "size": visual.encoding.size,
        }
        valid_encoding, encoding_errors = EncodingRequirements.validate_encoding(
            visual.visualization.type,
            encoding_dict
        )
        if not valid_encoding:
            for error_msg in encoding_errors:
                issues.append(ValidationIssue(
                    code="ENCODING_MISSING",
                    severity="warning",
                    message=f"Visual '{visual.id}': {error_msg}",
                    fix="Add required encoding axes to EncodingSpec"
                ))
        
        # Check 5: Data spec must reference valid fact table
        if not visual.data.fact_table:
            issues.append(ValidationIssue(
                code="DATA_NO_TABLE",
                severity="error",
                message=f"Visual '{visual.id}' has no fact_table specified",
                fix="Set data.fact_table to a valid table name"
            ))
        
        # Check 6: Chart subtype consistency
        if visual.rendering.rdl_type.endswith("Chart"):
            if not visual.rendering.chart_type:
                issues.append(ValidationIssue(
                    code="CHART_NO_SUBTYPE",
                    severity="warning",
                    message=f"Visual '{visual.id}' RDL type is '{visual.rendering.rdl_type}' but chart_type is missing",
                    fix="Set rendering.chart_type to Column, Bar, Line, Pie, etc."
                ))
        
        can_proceed = all(issue.severity != "error" for issue in issues)
        return can_proceed, issues
    
    def _validate_mapping(self, vis_type: str, rdl_type: str) -> tuple[bool, list[str]]:
        """Validate that visualization type matches RDL type"""
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
        
        if vis_type not in mapping:
            return False, [f"Unknown visualization type: {vis_type}"]
        
        expected_rdl = mapping[vis_type]
        if rdl_type != expected_rdl:
            return False, [
                f"RDL type mismatch: visualization type '{vis_type}' requires RDL type '{expected_rdl}', "
                f"got '{rdl_type}'"
            ]
        
        return True, []


class SpecValidator:
    """Validates collections of visuals"""
    
    def __init__(self):
        self.visual_validator = VisualSpecV2Validator()
    
    def validate_dashboard(self, pages: list[dict]) -> tuple[bool, list[ValidationIssue]]:
        """Validate all visuals in dashboard"""
        all_issues = []
        total_visuals = 0
        
        for page in pages:
            for visual_data in page.get("visuals", []):
                total_visuals += 1
                try:
                    # Try to build VisualSpecV2 - if construction fails, that's an error
                    visual = VisualSpecV2(**visual_data)
                    valid, issues = self.visual_validator.validate_single_visual(visual)
                    all_issues.extend(issues)
                except Exception as e:
                    all_issues.append(ValidationIssue(
                        code="SPEC_INVALID",
                        severity="error",
                        message=f"Visual construction failed: {str(e)}",
                        fix="Check visual specification structure"
                    ))
        
        can_proceed = all(issue.severity != "error" for issue in all_issues)
        return can_proceed, all_issues
