"""JSON Schemas for enhanced abstract specs"""
import json

ENCODING_AXIS_SCHEMA = {
    "type": "object",
    "properties": {
        "field": {"type": "string"},
        "aggregation": {
            "type": "string",
            "enum": ["SUM", "AVG", "COUNT", "MIN", "MAX", "NONE"]
        },
        "role": {
            "type": "string",
            "enum": ["dimension", "measure"]
        }
    },
    "required": ["field"],
    "additionalProperties": False
}

ENCODING_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "x": ENCODING_AXIS_SCHEMA,
        "y": ENCODING_AXIS_SCHEMA,
        "color": ENCODING_AXIS_SCHEMA,
        "size": ENCODING_AXIS_SCHEMA,
        "details": {
            "type": "array",
            "items": ENCODING_AXIS_SCHEMA
        }
    },
    "additionalProperties": False
}

VISUALIZATION_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["bar", "line", "pie", "treemap", "scatter", "table", "kpi", "map", "gantt"],
            "description": "Specific visualization type - NEVER 'chart'"
        },
        "encoding": ENCODING_SPEC_SCHEMA,
        "title": {"type": "string"},
        "description": {"type": "string"}
    },
    "required": ["type"],
    "additionalProperties": False
}

DATA_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "fact_table": {"type": "string"},
        "filters": {
            "type": "array",
            "items": {"type": "object"}
        },
        "joins": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["fact_table"],
    "additionalProperties": False
}

RENDERING_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "rdl_type": {
            "type": "string",
            "enum": [
                "ColumnChart", "BarChart", "LineChart", "PieChart", "TreeMap",
                "ScatterChart", "Tablix", "Textbox", "Map"
            ],
            "description": "Specific RDL type - NEVER generic 'Chart'"
        },
        "chart_type": {
            "type": ["string", "null"],
            "enum": ["Column", "Bar", "Line", "Pie", "Area", "Scatter", None]
        },
        "dimensions": {"type": "object"},
        "layout": {"type": "object"}
    },
    "required": ["rdl_type"],
    "additionalProperties": False
}

VISUAL_SPEC_V2_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "source_worksheet": {"type": "string"},
        "title": {"type": "string"},
        "visualization": VISUALIZATION_SPEC_SCHEMA,
        "encoding": ENCODING_SPEC_SCHEMA,
        "data": DATA_SPEC_SCHEMA,
        "rendering": RENDERING_SPEC_SCHEMA,
        "position": {"type": "object"},
        "metadata": {"type": "object"}
    },
    "required": ["id", "source_worksheet", "title", "visualization", "encoding", "data", "rendering"],
    "additionalProperties": False,
    "description": "Enhanced visual specification with strict separation of concerns"
}

DASHBOARD_PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "visuals": {
            "type": "array",
            "items": VISUAL_SPEC_V2_SCHEMA
        }
    },
    "required": ["id", "name", "visuals"],
    "additionalProperties": False
}

DASHBOARD_SPEC_V2_SCHEMA = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": DASHBOARD_PAGE_SCHEMA
        },
        "theme": {"type": "object"},
        "global_filters": {
            "type": "array",
            "items": {"type": "object"}
        }
    },
    "required": ["pages"],
    "additionalProperties": False,
    "description": "Dashboard specification with strict validation"
}


def get_schema_string(schema_name: str) -> str:
    """Get JSON schema as a formatted string"""
    schemas = {
        "encoding_axis": ENCODING_AXIS_SCHEMA,
        "encoding_spec": ENCODING_SPEC_SCHEMA,
        "visualization_spec": VISUALIZATION_SPEC_SCHEMA,
        "data_spec": DATA_SPEC_SCHEMA,
        "rendering_spec": RENDERING_SPEC_SCHEMA,
        "visual_spec_v2": VISUAL_SPEC_V2_SCHEMA,
        "dashboard_page": DASHBOARD_PAGE_SCHEMA,
        "dashboard_spec_v2": DASHBOARD_SPEC_V2_SCHEMA,
    }
    
    if schema_name not in schemas:
        raise ValueError(f"Unknown schema: {schema_name}")
    
    return json.dumps(schemas[schema_name], indent=2)


def save_schemas(output_dir: str) -> None:
    """Save all schemas to JSON files"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    schemas_to_save = {
        "encoding_axis.schema.json": ENCODING_AXIS_SCHEMA,
        "encoding_spec.schema.json": ENCODING_SPEC_SCHEMA,
        "visualization_spec.schema.json": VISUALIZATION_SPEC_SCHEMA,
        "data_spec.schema.json": DATA_SPEC_SCHEMA,
        "rendering_spec.schema.json": RENDERING_SPEC_SCHEMA,
        "visual_spec_v2.schema.json": VISUAL_SPEC_V2_SCHEMA,
        "dashboard_page.schema.json": DASHBOARD_PAGE_SCHEMA,
        "dashboard_spec_v2.schema.json": DASHBOARD_SPEC_V2_SCHEMA,
    }
    
    for filename, schema in schemas_to_save.items():
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"Saved: {filepath}")
