import test from "node:test";
import assert from "node:assert/strict";

import { FederatedDatasourceResolver } from "../../src/tableau/federated-datasource-resolver.js";
import type { ParsedWorkbook } from "../../src/tableau/interfaces.js";

const parsedWorkbook: ParsedWorkbook = {
  worksheets: [
    {
      id: "ws1",
      name: "Sheet1",
      rows: ["federated.abc123.sum:Sales Amount:qk"],
      cols: ["federated.abc123.none:Category:nk"],
      marks: ["bar"],
      filters: [],
    },
  ],
  datasources: [
    {
      id: "federated.abc123",
      name: "FederatedDS",
      tables: [{ name: "unknown_table" }],
      columns: [
        { id: "[Sales Amount]", name: "Sales Amount", dataType: "real" },
        { id: "[Category]", name: "Category", dataType: "string" },
        { id: "[Customer_data]", name: "Customer_data", dataType: "string" },
        { id: "[Sales_data]", name: "Sales_data", dataType: "string" },
      ],
    },
  ],
  calculated_fields: [],
  dashboards: [],
  parameters: [],
};

const workbookNode = {
  datasources: {
    datasource: [
      {
        name: "federated.abc123",
        connection: {
          "named-connections": {
            "named-connection": [
              { name: "Customer" },
              { name: "Sales" },
            ],
          },
        },
      },
    ],
  },
};

test("resout datasource federated et decode tokens bruts", () => {
  const resolver = new FederatedDatasourceResolver();
  const resolved = resolver.resolve(parsedWorkbook, workbookNode as Record<string, unknown>);

  const tables = resolved.datasources[0]?.tables.map((table) => table.name) ?? [];
  assert.equal(tables.includes("unknown_table"), false);
  assert.ok(tables.includes("customer_data") || tables.includes("sales_data"));

  const decodedRow = resolved.worksheets[0]?.rows[0] ?? "";
  const decodedCol = resolved.worksheets[0]?.cols[0] ?? "";
  assert.equal(decodedRow.startsWith("sum("), true);
  assert.equal(decodedCol.includes("."), true);
  assert.equal(decodedRow.includes("federated."), false);
  assert.equal(decodedCol.includes("federated."), false);
});
