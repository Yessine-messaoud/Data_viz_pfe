import test from "node:test";
import assert from "node:assert/strict";
import { generateSQL } from "../../src/lineage/sql-generator.js";
const spec = {
    id: "spec-1",
    version: "0.1.0",
    source_fingerprint: "abc",
    dashboard_spec: {
        pages: [],
        global_filters: [],
        theme: { name: "demo", palette: ["#111"] },
        refresh_policy: { mode: "manual" },
    },
    semantic_model: {
        entities: [],
        measures: [],
        dimensions: [],
        hierarchies: [],
        relationships: [],
        glossary: [],
        fact_table: "sales_data",
        grain: "row",
    },
    data_lineage: {
        tables: [{ id: "t1", name: "sales_data" }],
        joins: [],
        columns_used: [],
        visual_column_map: {
            v1: {
                columns: [{ table: "sales_data", column: "Amount" }],
                joins_used: [],
                filters: [],
            },
        },
    },
    export_manifest: {
        target: "powerbi",
        model_config: { dataset_name: "d" },
        dax_measures: [],
        m_queries: [],
        post_export_hooks: [],
    },
    build_log: [],
    warnings: [],
};
test("genere SQL depuis lineage visual", () => {
    const sql = generateSQL(spec, "v1");
    assert.match(sql, /FROM \[sales_data\]/);
    assert.match(sql, /\[sales_data\]\.\[Amount\]/);
});
test("genere SQL fallback si aucune colonne n'est disponible", () => {
    const noColumnsSpec = {
        ...spec,
        data_lineage: {
            ...spec.data_lineage,
            visual_column_map: {
                v2: {
                    columns: [],
                    joins_used: [],
                    filters: [],
                },
            },
        },
    };
    const sql = generateSQL(noColumnsSpec, "v2");
    assert.match(sql, /COUNT\(1\) AS \[row_count\]/);
    assert.match(sql, /FROM \[sales_data\]/);
});
