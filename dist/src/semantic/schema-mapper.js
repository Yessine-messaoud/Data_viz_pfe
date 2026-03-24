const TYPE_MAP = {
    string: "text",
    integer: "int64",
    int: "int64",
    float: "double",
    real: "double",
    double: "double",
    boolean: "boolean",
    date: "date",
    datetime: "dateTime",
};
const VISUAL_MAP = {
    bar: "bar",
    sidebysidebars: "bar",
    line: "line",
    area: "area",
    pie: "pie",
    scatter: "scatter",
    texttable: "table",
    map: "map",
    symbolmap: "map",
    kpi: "kpi",
    card: "card",
    treemap: "treemap",
    heatmap: "heatmap",
    combo: "combo",
};
export class DefaultSchemaMapper {
    mapTypes(tableauType) {
        return TYPE_MAP[tableauType.toLowerCase()] ?? "text";
    }
    mapVisualType(tableauVisualType) {
        return VISUAL_MAP[tableauVisualType.toLowerCase()] ?? "table";
    }
}
