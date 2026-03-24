import type { ColumnRef, DataLineageSpec, JoinDef, MeasureDef } from "../spec/abstract-spec.js";
export interface SQLVisualEquivalent {
    visual_id: string;
    sql: string;
}
export interface LineageJson {
    tables: DataLineageSpec["tables"];
    full_tables?: DataLineageSpec["full_tables"];
    sampled_rows?: DataLineageSpec["sampled_rows"];
    full_table_profiles?: DataLineageSpec["full_table_profiles"];
    joins: JoinDef[];
    visual_column_map: DataLineageSpec["visual_column_map"];
    measures: MeasureDef[];
    sql_equivalents: SQLVisualEquivalent[];
}
export interface LineageQueryServiceV2 {
    getTablesForVisual(visualId: string): string[];
    getJoin(joinId: string): JoinDef | undefined;
    getVisualsForColumn(column: ColumnRef): string[];
}
