"""Migration adapter: Convert old abstract spec structure to new V2 structure"""
from __future__ import annotations
from typing import Any


class SpecMigrationAdapter:
    """Adapts old spec structure to new VisualSpecV2 structure"""
    
    @staticmethod
    def migrate_visual_old_to_v2(old_visual: dict) -> dict:
        """
        Convert old visual structure to new V2 structure
        
        Old structure:
        {
            "id": "...",
            "type": "pie",
            "rdl_type": "chart",
            "data_binding": {...},
            "title": "..."
        }
        
        New structure:
        {
            "id": "...",
            "title": "...",
            "visualization": {"type": "pie", "encoding": {}},
            "encoding": {"x": ..., "y": ..., "color": ..., "size": ...},
            "data": {"fact_table": "...", "filters": [], "joins": []},
            "rendering": {"rdl_type": "PieChart", "chart_type": "Pie", ...}
        }
        """
        
        visual_id = old_visual.get("id", "unknown")
        source_worksheet = old_visual.get("source_worksheet", visual_id)
        title = old_visual.get("title", "")
        old_type = old_visual.get("type", "table")
        old_rdl_type = old_visual.get("rdl_type", "tablix")
        position = old_visual.get("position", {})
        
        # Extract data binding
        data_binding = old_visual.get("data_binding", {})
        axes = data_binding.get("axes", {})
        measures = data_binding.get("measures", [])
        filters = data_binding.get("filters", [])
        
        # Build encoding from axes and measures
        x_encoding = SpecMigrationAdapter._axis_to_encoding(axes.get("x")) if axes.get("x") else None
        y_encoding = SpecMigrationAdapter._axis_to_encoding(axes.get("y")) if axes.get("y") else None
        
        # For pie charts, if we don't have Y encoding but have measures, use first measure
        if old_type == "pie" and not y_encoding and measures:
            first_measure = measures[0] if isinstance(measures, list) else measures
            if isinstance(first_measure, dict):
                measure_name = first_measure.get("name", "Measure")
                y_encoding = {
                    "field": measure_name,
                    "aggregation": "SUM",
                    "role": "measure"
                }
            else:
                y_encoding = {
                    "field": str(first_measure),
                    "aggregation": "SUM",
                    "role": "measure"
                }
        
        encoding = {
            "x": x_encoding,
            "y": y_encoding,
            "color": axes.get("color"),
            "size": axes.get("size"),
            "details": []
        }
        
        # Build visualization spec
        visualization = {
            "type": old_type,
            "encoding": encoding,
            "title": title
        }
        
        # Build data spec - need to find fact table from somewhere
        # For now, use a placeholder that will be filled in
        data = {
            "fact_table": "federated.unknown",  # Will be determined from context
            "filters": filters,
            "joins": []
        }
        
        # Build rendering spec
        # Map old rdl_type to new one
        rendering = {
            "rdl_type": SpecMigrationAdapter._map_old_rdl_type_to_new(old_type, old_rdl_type),
            "chart_type": None,
            "dimensions": {},
            "layout": {}
        }
        
        # Set chart_type if applicable
        if rendering["rdl_type"].endswith("Chart"):
            chart_subtype_map = {
                "ColumnChart": "Column",
                "BarChart": "Bar",
                "LineChart": "Line",
                "PieChart": "Pie",
                "ScatterChart": "Scatter",
                "AreaChart": "Area",
            }
            rendering["chart_type"] = chart_subtype_map.get(rendering["rdl_type"])
        
        # Build new visual spec
        new_visual = {
            "id": visual_id,
            "source_worksheet": source_worksheet,
            "title": title,
            "visualization": visualization,
            "encoding": encoding,
            "data": data,
            "rendering": rendering,
            "position": position,
            "metadata": {"migrated": True, "original_type": old_type, "original_rdl_type": old_rdl_type}
        }
        
        return new_visual
    
    @staticmethod
    def _axis_to_encoding(axis: Any) -> dict | None:
        """Convert axis ref to encoding axis"""
        if not axis:
            return None
        
        if isinstance(axis, dict):
            return {
                "field": axis.get("column", axis.get("name", "Unknown")),
                "aggregation": "NONE",
                "role": "dimension"
            }
        elif hasattr(axis, "column"):
            return {
                "field": str(axis.column),
                "aggregation": "NONE",
                "role": "dimension"
            }
        elif hasattr(axis, "name"):
            return {
                "field": str(axis.name),
                "aggregation": "NONE" if not hasattr(axis, "aggregation") else str(axis.aggregation),
                "role": "measure" if "measure" in str(getattr(axis, "role", "")).lower() else "dimension"
            }
        
        return None
    
    @staticmethod
    def _map_old_rdl_type_to_new(logical_type: str, old_rdl_type: str) -> str:
        """Map old RDL type (often generic 'chart') to new specific type"""
        
        # If old_rdl_type is already specific, return it
        specific_types = [
            "ColumnChart", "BarChart", "LineChart", "PieChart", "TreeMap",
            "ScatterChart", "Tablix", "Textbox", "Map"
        ]
        if old_rdl_type in specific_types:
            return old_rdl_type
        
        # Map logical type to RDL type
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
        
        return mapping.get(logical_type.lower(), "Tablix")
    
    @staticmethod
    def migrate_dashboard_old_to_v2(old_dashboard: dict) -> dict:
        """Migrate entire dashboard spec from old to new structure"""
        new_pages = []
        
        old_pages = old_dashboard.get("pages", [])
        for page in old_pages:
            new_page = {
                "id": page.get("id"),
                "name": page.get("name"),
                "visuals": [
                    SpecMigrationAdapter.migrate_visual_old_to_v2(visual)
                    for visual in page.get("visuals", [])
                ]
            }
            new_pages.append(new_page)
        
        new_dashboard = {
            "pages": new_pages,
            "theme": old_dashboard.get("theme", {}),
            "global_filters": old_dashboard.get("global_filters", [])
        }
        
        return new_dashboard
    
    @staticmethod
    def migrate_spec_old_to_v2(old_spec: dict) -> dict:
        """Migrate entire abstract spec from old to new structure"""
        new_spec = {
            "id": old_spec.get("id"),
            "version": "2.1.0",  # New version with migration
            "created_at": old_spec.get("created_at"),
            "source_fingerprint": old_spec.get("source_fingerprint"),
            "dashboard_spec": SpecMigrationAdapter.migrate_dashboard_old_to_v2(
                old_spec.get("dashboard_spec", {})
            ),
            "semantic_model": old_spec.get("semantic_model", {}),
            "data_lineage": old_spec.get("data_lineage", {}),
            "rdl_datasets": old_spec.get("rdl_datasets", []),
            "migration_metadata": {
                "migrated_from_version": old_spec.get("version", "unknown"),
                "migration_note": "Migrated from flat structure to layered V2 structure"
            }
        }
        
        return new_spec


def patch_fact_table_in_migrated_spec(migrated_spec: dict, fact_table: str) -> dict:
    """Patch the fact_table in migrated spec (which was unknown during migration)"""
    pages = migrated_spec.get("dashboard_spec", {}).get("pages", [])
    
    for page in pages:
        for visual in page.get("visuals", []):
            data = visual.get("data", {})
            if data.get("fact_table", "").startswith("federated.unknown"):
                data["fact_table"] = fact_table
    
    return migrated_spec
