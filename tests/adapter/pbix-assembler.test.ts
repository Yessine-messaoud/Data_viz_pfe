import test from "node:test";
import assert from "node:assert/strict";
import AdmZip from "adm-zip";

import { PBIXAssembler } from "../../src/adapter/pbix-assembler.js";
import type { AbstractSpec } from "../../src/spec/abstract-spec.js";

const spec: AbstractSpec = {
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
  data_lineage: { tables: [], joins: [], columns_used: [], visual_column_map: {} },
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

test("assemble pbix zip avec structure attendue", () => {
  const assembler = new PBIXAssembler();
  const result = assembler.assemble(spec);

  const zip = new AdmZip(Buffer.from(result.bytes));
  const names = zip.getEntries().map((entry) => entry.entryName);

  assert.ok(names.includes("[Content_Types].xml"));
  assert.ok(names.includes("DataModel/model.json"));
  assert.ok(names.includes("Report/layout.json"));
  assert.ok(names.includes("theme.json"));
  assert.ok(names.includes("connections.json"));
});
