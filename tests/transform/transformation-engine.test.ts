import test from "node:test";
import assert from "node:assert/strict";

import { DefaultTransformationEngine } from "../../src/transform/transformation-engine.js";
import type { DataLineageSpec, SemanticModel } from "../../src/spec/abstract-spec.js";

const model: SemanticModel = {
  entities: [],
  measures: [{ name: "Total Sales", expression: "SUM(Sales[Amount])" }],
  dimensions: [{ name: "Customer", source: { table: "customer_data", column: "Customer" } }],
  hierarchies: [],
  relationships: [],
  glossary: [],
  fact_table: "sales_data",
  grain: "row",
};

const lineage: DataLineageSpec = {
  tables: [
    { id: "t1", name: "sales_data" },
    { id: "t2", name: "customer_data" },
  ],
  joins: [],
  columns_used: [{ visual_id: "v1", column: { table: "customer_data", column: "Customer" }, usage: "axis" }],
  visual_column_map: { v1: { columns: [{ table: "customer_data", column: "Customer" }], joins_used: [], filters: [] } },
  full_table_profiles: [
    {
      table_name: "sales_data",
      columns: [
        { name: "Customer", type: "string" },
        { name: "Amount", type: "number" },
      ],
      sample_data: [
        { Customer: "A", Amount: 10 },
        { Customer: "B", Amount: 20 },
      ],
      source: "hyper",
    },
  ],
};

test("orchestration phase 5 produit export manifest avec m queries et dax", () => {
  const engine = new DefaultTransformationEngine();
  const result = engine.run(["add filter region", "rename column customer"], model, lineage);

  assert.equal(result.ops.length > 0, true);
  assert.equal(result.exportManifest.target, "powerbi");
  assert.equal(result.exportManifest.m_queries.length > 0, true);
  assert.equal(result.exportManifest.m_queries.some((query) => query.name === "Dataset_sales_data"), true);
  assert.equal(result.exportManifest.m_queries.some((query) => query.name === "Dataset_customer_data"), true);
  assert.equal(result.exportManifest.dax_measures.length > 0, true);
});

test("genere une requete M #table depuis full_table_profiles", () => {
  const engine = new DefaultTransformationEngine();
  const result = engine.run(["normalize schema"], model, lineage);

  const salesDataset = result.exportManifest.m_queries.find((query) => query.name === "Dataset_sales_data");
  assert.notEqual(salesDataset, undefined);
  assert.match(salesDataset?.query ?? "", /#table\(/);
  assert.match(salesDataset?.query ?? "", /Customer/);
  assert.match(salesDataset?.query ?? "", /Amount/);
});
