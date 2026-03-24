import test from "node:test";
import assert from "node:assert/strict";

import { LineageQueryServiceImpl } from "../../src/lineage/lineage-query-service-v2.js";
import type { LineageJson } from "../../src/lineage/lineage-spec.js";

const lineage: LineageJson = {
  tables: [{ id: "t1", name: "sales_data" }],
  joins: [],
  measures: [],
  sql_equivalents: [],
  visual_column_map: {
    v1: {
      columns: [{ table: "sales_data", column: "Amount" }],
      joins_used: [],
      filters: [],
    },
  },
};

test("query service lineage v2 repond aux requetes de base", () => {
  const service = new LineageQueryServiceImpl(lineage);
  assert.deepEqual(service.getTablesForVisual("v1"), ["sales_data"]);
  assert.deepEqual(service.getVisualsForColumn({ table: "sales_data", column: "Amount" }), ["v1"]);
});
