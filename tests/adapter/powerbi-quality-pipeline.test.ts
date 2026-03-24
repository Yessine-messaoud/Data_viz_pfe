import test from "node:test";
import assert from "node:assert/strict";

import { PBIXTemplate, PowerBIQualityPipeline } from "../../src/adapter/powerbi-quality-pipeline.js";
import { PBIXAssembler } from "../../src/adapter/pbix-assembler.js";
import type { AbstractSpec } from "../../src/spec/abstract-spec.js";

function createBaseSpec(): AbstractSpec {
  return {
    id: "spec-quality",
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
      measures: [{ name: "Sales", expression: "SUMIF([Sales].[Amount], [Sales].[Amount] > 0)" }],
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
      model_config: { dataset_name: "dataset_demo" },
      dax_measures: [{ name: "Sales", expression: "SUMIF([Sales].[Amount], [Sales].[Amount] > 0)" }],
      m_queries: [{ name: "sales_data", query: "let Source = 1 in Source" }],
      post_export_hooks: [],
    },
    build_log: [],
    warnings: [],
  };
}

test("PBIXTemplate ajoute un scaffold minimal valide", () => {
  const template = new PBIXTemplate();
  const zip = template.createBaseArchive(createBaseSpec());
  const names = zip.getEntries().map((entry) => entry.entryName);

  assert.ok(names.includes("[Content_Types].xml"));
  assert.ok(names.includes("Metadata/version.json"));
});

test("pipeline applique autofix DAX et conserve un spec valide", () => {
  const pipeline = new PowerBIQualityPipeline();
  const result = pipeline.prepareSpec(createBaseSpec());

  assert.equal(result.valid, true);
  assert.equal(result.warnings.length > 0, true);
  assert.equal(result.fixedSpec.export_manifest.dax_measures[0]?.expression.includes("SUMIF"), false);
});

test("pipeline n'interprete pas les labels de colonnes comme fonctions DAX", () => {
  const pipeline = new PowerBIQualityPipeline();
  const spec = createBaseSpec();
  const expression = "SUM(CustomerKey (Customer!data))";

  spec.export_manifest.dax_measures = [{ name: "LabelMeasure", expression }];
  spec.data_lineage.columns_used = [{
    visual_id: "v1",
    column: { table: "Customer!data", column: "CustomerKey" },
    usage: "measure",
  }];

  const result = pipeline.prepareSpec(spec);
  assert.equal(result.valid, true);
  assert.equal(result.issues.length, 0);
});

test("pipeline detecte les erreurs de modele", () => {
  const pipeline = new PowerBIQualityPipeline();
  const invalidSpec = {
    ...createBaseSpec(),
    semantic_model: {
      ...createBaseSpec().semantic_model,
      fact_table: "missing_table",
    },
  } satisfies AbstractSpec;

  const result = pipeline.prepareSpec(invalidSpec);
  assert.equal(result.valid, true);
  assert.ok(result.warnings.some((warning) => warning.code === "M_FACT_AUTOFIX"));
  assert.equal(result.fixedSpec.semantic_model.fact_table, "sales_data");
});

test("FIX1 M_FACT applique autofix sur fact_table incoherente", () => {
  const pipeline = new PowerBIQualityPipeline();
  const spec = createBaseSpec();

  spec.semantic_model.fact_table = "customer_data";
  spec.data_lineage.tables = [
    { id: "t_customer", name: "customer_data" },
    { id: "t_sales", name: "sales_data" },
  ];
  spec.data_lineage.joins = [
    {
      id: "j1",
      left_table: "sales_data",
      right_table: "customer_data",
      type: "inner",
      keys: [
        {
          left: { table: "sales_data", column: "CustomerKey" },
          right: { table: "customer_data", column: "CustomerKey" },
        },
      ],
    },
  ];
  spec.data_lineage.full_table_profiles = [
    {
      table_name: "customer_data",
      source: "xml",
      columns: [
        { name: "CustomerKey", type: "integer" },
        { name: "CustomerName", type: "string" },
      ],
      sample_data: [],
    },
    {
      table_name: "sales_data",
      source: "xml",
      columns: [
        { name: "CustomerKey", type: "integer" },
        { name: "DateKey", type: "integer" },
        { name: "ProductKey", type: "integer" },
        { name: "SalesAmount", type: "double" },
        { name: "TotalCost", type: "double" },
      ],
      sample_data: [],
    },
  ];

  const result = pipeline.prepareSpec(spec);
  assert.equal(result.valid, true);
  assert.equal(result.fixedSpec.semantic_model.fact_table, "sales_data");
  assert.equal(result.warnings.some((warning) => warning.code === "M_FACT_AUTOFIX"), true);
});

test("pipeline valide les bytes PBIX assembles", () => {
  const pipeline = new PowerBIQualityPipeline();
  const assembler = new PBIXAssembler();
  const assembled = assembler.assemble(createBaseSpec());

  const pbixIssues = pipeline.validatePbix(assembled.bytes);
  assert.equal(pbixIssues.length, 0);
});
