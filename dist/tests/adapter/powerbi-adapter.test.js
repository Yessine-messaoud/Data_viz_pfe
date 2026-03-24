import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { PowerBIAdapter } from "../../src/adapter/powerbi-adapter.js";
const validSpec = {
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
        columns_used: [{ visual_id: "v1", column: { table: "sales_data", column: "Amount" }, usage: "measure" }],
        visual_column_map: {},
    },
    export_manifest: {
        target: "powerbi",
        model_config: { dataset_name: "d" },
        dax_measures: [{ name: "Sales", expression: "SUM(Sales[Amount])" }],
        m_queries: [{ name: "sales_data", query: "let Source = 1 in Source" }],
        post_export_hooks: [],
    },
    build_log: [],
    warnings: [],
};
test("validate/build/deploy local de powerbi adapter", async () => {
    const adapter = new PowerBIAdapter();
    const validation = adapter.validate(validSpec);
    assert.equal(validation.valid, true);
    const out = await mkdtemp(path.join(os.tmpdir(), "coeur-adapter-"));
    const build = await adapter.build(validSpec, out);
    assert.ok(build.artifactPath.endsWith(".pbix"));
    const deploy = await adapter.deploy(build);
    assert.equal(deploy.success, true);
    await rm(out, { recursive: true, force: true });
});
