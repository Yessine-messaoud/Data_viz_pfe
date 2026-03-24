import { generateSQL } from "./sql-generator.js";
export function buildLineageJson(spec) {
    const sql_equivalents = Object.keys(spec.data_lineage.visual_column_map).map((visual_id) => ({
        visual_id,
        sql: generateSQL(spec, visual_id),
    }));
    return {
        tables: spec.data_lineage.tables,
        full_tables: spec.data_lineage.full_tables,
        sampled_rows: spec.data_lineage.sampled_rows,
        full_table_profiles: spec.data_lineage.full_table_profiles,
        joins: spec.data_lineage.joins,
        visual_column_map: spec.data_lineage.visual_column_map,
        measures: spec.semantic_model.measures,
        sql_equivalents,
    };
}
