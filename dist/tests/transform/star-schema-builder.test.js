import test from "node:test";
import assert from "node:assert/strict";
import { SemanticStarSchemaBuilder } from "../../src/transform/star-schema-builder.js";
const model = {
    entities: [],
    measures: [{ name: "Total Sales", expression: "SUM(Sales[Amount])" }],
    dimensions: [
        { name: "Customer", source: { table: "customer_data", column: "Customer" } },
        { name: "Date", source: { table: "date_data", column: "Date" } },
    ],
    hierarchies: [],
    relationships: [],
    glossary: [],
    fact_table: "sales_data",
    grain: "row",
};
const lineage = {
    tables: [
        { id: "t1", name: "sales_data" },
        { id: "t2", name: "customer_data" },
    ],
    joins: [],
    columns_used: [{ visual_id: "v1", column: { table: "date_data", column: "Date" }, usage: "axis" }],
    visual_column_map: { v1: { columns: [{ table: "date_data", column: "Date" }], joins_used: [], filters: [] } },
};
test("construit un schema en etoile avec dimensions", () => {
    const builder = new SemanticStarSchemaBuilder();
    const schema = builder.build(model, lineage);
    assert.equal(schema.factTable, "sales_data");
    assert.equal(schema.dimensions.length >= 1, true);
});
