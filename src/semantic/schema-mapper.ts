import type { SchemaMapper } from "./interfaces.js";

const TYPE_MAP: Record<string, string> = {
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

const VISUAL_MAP: Record<string, "bar" | "line" | "area" | "pie" | "scatter" | "table" | "map" | "kpi" | "card" | "treemap" | "heatmap" | "combo"> = {
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

export class DefaultSchemaMapper implements SchemaMapper {
  public mapTypes(tableauType: string): string {
    return TYPE_MAP[tableauType.toLowerCase()] ?? "text";
  }

  public mapVisualType(tableauVisualType: string) {
    return VISUAL_MAP[tableauVisualType.toLowerCase()] ?? "table";
  }
}
