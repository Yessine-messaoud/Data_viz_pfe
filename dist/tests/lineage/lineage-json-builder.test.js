import test from "node:test";
import assert from "node:assert/strict";
import { buildLineageJson } from "../../src/lineage/lineage-json-builder.js";
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
        measures: [{ name: "Sales", expression: "SUM(Sales[Amount])" }],
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
test("construit lineage.json incluant sql equivalents", () => {
    const lineage = buildLineageJson(spec);
    assert.equal(lineage.tables.length, 1);
    assert.equal(lineage.sql_equivalents.length, 1);
    assert.match(lineage.sql_equivalents[0]?.sql ?? "", /SELECT/);
});
