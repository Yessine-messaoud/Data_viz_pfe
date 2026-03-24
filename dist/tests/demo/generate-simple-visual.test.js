import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { generateSimpleVisualFromAbstractJson } from "../../src/demo/generate-simple-visual.js";
const minimalSpec = {
    id: "spec-1",
    version: "0.1.0",
    source_fingerprint: "abc123",
    dashboard_spec: {
        pages: [
            {
                id: "page-1",
                name: "Main",
                visuals: [
                    {
                        id: "v1",
                        source_worksheet: "Sheet1",
                        type: "bar",
                        position: { row: 0, column: 0, row_span: 1, column_span: 1 },
                        data_binding: { axes: { x: { table: "t", column: "c1" }, y: { table: "t", column: "c2" } } },
                        title: "Sales by Region",
                    },
                ],
            },
        ],
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
        fact_table: "fact_sales",
        grain: "row",
    },
    data_lineage: {
        tables: [{ id: "t1", name: "fact_sales" }],
        full_tables: [{ id: "ft1", name: "fact_sales" }],
        full_table_profiles: [
            {
                table_name: "fact_sales",
                source: "xml",
                columns: [
                    { name: "id", type: "integer" },
                    { name: "amount", type: "real" },
                    { name: "customer_id", type: "integer" },
                ],
                sample_data: [
                    { id: 1, amount: 100, customer_id: 10 },
                    { id: 2, amount: 120, customer_id: 11 },
                ],
            },
        ],
        sampled_rows: {
            fact_sales: [
                { id: 1, amount: 100, customer_id: 10 },
                { id: 2, amount: 120, customer_id: 11 },
            ],
        },
        joins: [],
        columns_used: [],
        visual_column_map: {},
    },
    export_manifest: {
        target: "powerbi",
        model_config: { dataset_name: "demo" },
        dax_measures: [],
        m_queries: [],
        post_export_hooks: [],
    },
    build_log: [],
    warnings: [],
};
test("genere un html visuel simple depuis abstract json", async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), "coeur-visual-"));
    const outputDir = path.join(root, "output");
    await mkdir(outputDir, { recursive: true });
    await writeFile(path.join(outputDir, "abstract-visualization.json"), JSON.stringify(minimalSpec, null, 2), "utf8");
    const htmlPath = await generateSimpleVisualFromAbstractJson(root);
    const html = await readFile(htmlPath, "utf8");
    assert.ok(html.includes("Visualisation Abstraite"));
    assert.ok(html.includes("Sales by Region"));
    assert.ok(html.includes("Schema Graph"));
    assert.ok(html.includes("Preuve par couche"));
    assert.ok(html.includes("1) Parse Tableau"));
    assert.ok(html.includes("3) Build AbstractSpec (pivot)"));
    assert.ok(html.includes("Proof Report"));
    assert.ok(html.includes("Layer Status"));
    assert.ok(html.includes("Artifact Status"));
    assert.ok(html.includes("Pipeline:"));
    assert.ok(html.includes("TWBX/HYPER Extraction Proof"));
    assert.ok(html.includes("Datasource Tables Preview (head 5)"));
    assert.ok(html.includes("TABLE:"));
    await rm(root, { recursive: true, force: true });
});
