import test from "node:test";
import assert from "node:assert/strict";

import { AbstractSpecBuilder } from "../../src/spec/abstract-spec-builder.js";
import type { BuildIntent, DataLineageSpec, SemanticModel, WorkbookInput } from "../../src/spec/abstract-spec.js";

const workbook: WorkbookInput = {
  raw: "<workbook><worksheet name=\"Sales\" /></workbook>",
  source_name: "sales-dashboard",
};

const intent: BuildIntent = {
  target: "powerbi",
  description: "Convert dashboard",
  modifications: ["map visuals", "keep semantics"],
};

const semanticModel: SemanticModel = {
  entities: [{ name: "Sales", source: { table: "fact_sales", column: "sales_amount" } }],
  measures: [{ name: "Total Sales", expression: "SUM(fact_sales[sales_amount])" }],
  dimensions: [{ name: "Country", source: { table: "dim_geo", column: "country" } }],
  hierarchies: [
    {
      name: "Date",
      levels: [
        { name: "Year", column: { table: "dim_date", column: "year" } },
        { name: "Month", column: { table: "dim_date", column: "month" } },
      ],
    },
  ],
  relationships: [
    {
      from: { table: "fact_sales", column: "date_key" },
      to: { table: "dim_date", column: "date_key" },
      cardinality: "many-to-one",
      cross_filter_direction: "single",
    },
  ],
  glossary: [{ term: "GMV", definition: "Gross Merchandise Value" }],
  fact_table: "fact_sales",
  grain: "one row per order line",
};

const lineage: DataLineageSpec = {
  tables: [
    { id: "t1", name: "fact_sales" },
    { id: "t2", name: "dim_date" },
  ],
  joins: [
    {
      id: "j1",
      left_table: "fact_sales",
      right_table: "dim_date",
      type: "inner",
      keys: [{ left: { table: "fact_sales", column: "date_key" }, right: { table: "dim_date", column: "date_key" } }],
    },
  ],
  columns_used: [
    {
      visual_id: "v1",
      column: { table: "fact_sales", column: "sales_amount" },
      usage: "measure",
    },
  ],
  visual_column_map: {
    v1: {
      columns: [{ table: "fact_sales", column: "sales_amount" }],
      joins_used: ["j1"],
      filters: [],
    },
  },
};

test("serialisation JSON sans perte", () => {
  const builder = new AbstractSpecBuilder();
  const spec = builder.build(workbook, intent, semanticModel, lineage);

  const serialized = JSON.stringify(spec);
  const parsed = JSON.parse(serialized) as typeof spec;

  assert.deepEqual(parsed, spec);
});

test("ID stable pour memes entrees", () => {
  const builder = new AbstractSpecBuilder();
  const first = builder.build(workbook, intent, semanticModel, lineage);
  const second = builder.build(workbook, intent, semanticModel, lineage);

  assert.equal(first.id, second.id);
  assert.equal(first.source_fingerprint, second.source_fingerprint);
});
