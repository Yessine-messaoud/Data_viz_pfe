import test from "node:test";
import assert from "node:assert/strict";

import { PowerQueryMBuilder } from "../../src/transform/m-query-builder.js";
import type { StarSchemaModel, TransformOp } from "../../src/transform/interfaces.js";

const ops: TransformOp[] = [
  { id: "op_1", order: 1, type: "normalize-schema", payload: {}, source: "system" },
  { id: "op_2", order: 2, type: "add-filter", payload: {}, source: "intent" },
];

const schema: StarSchemaModel = {
  factTable: "sales_data",
  dimensions: [{ name: "customer_data", keyColumn: "customer_key", sourceColumns: [{ table: "customer_data", column: "Customer" }] }],
  bridges: [],
  hasAutoDateDimension: false,
};

test("genere des requetes M a partir des operations", () => {
  const builder = new PowerQueryMBuilder();
  const plan = builder.build(ops, schema);

  assert.equal(plan.queries.length >= 2, true);
  assert.equal(plan.queries[0]?.name, "sales_data");
});
