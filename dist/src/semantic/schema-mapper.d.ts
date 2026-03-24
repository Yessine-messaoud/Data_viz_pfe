import type { SchemaMapper } from "./interfaces.js";
export declare class DefaultSchemaMapper implements SchemaMapper {
    mapTypes(tableauType: string): string;
    mapVisualType(tableauVisualType: string): "bar" | "line" | "area" | "pie" | "scatter" | "table" | "map" | "kpi" | "card" | "treemap" | "heatmap" | "combo";
}
