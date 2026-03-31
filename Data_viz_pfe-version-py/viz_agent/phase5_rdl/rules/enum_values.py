from __future__ import annotations

VALID_ENUMS = {
    "TextAlign": {"Left", "Center", "Right", "Justify", "General"},
    "VerticalAlign": {"Top", "Middle", "Bottom"},
    "BorderStyle": {"None", "Solid", "Dashed", "Dotted", "Double", "DashDot", "DashDotDot"},
    "Orientation": {"Landscape", "Portrait"},
    "DataType": {"String", "Boolean", "DateTime", "Integer", "Float", "Binary"},
    "SortDirection": {"Ascending", "Descending"},
}

NUMERIC_ELEMENTS = {
    "Width",
    "Height",
    "Top",
    "Left",
    "MarginTop",
    "MarginBottom",
    "MarginLeft",
    "MarginRight",
    "PageWidth",
    "PageHeight",
    "ColumnWidth",
    "RowHeight",
}
