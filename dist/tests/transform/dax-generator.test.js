import test from "node:test";
import assert from "node:assert/strict";
import { TemplateDaxGenerator } from "../../src/transform/dax-generator.js";
const model = {
    entities: [],
    measures: [
        { name: "Simple", expression: "SUM(Sales[Amount])" },
        { name: "Complex", expression: "{ FIXED [Region]: SUM([Sales]) }" },
    ],
    dimensions: [],
    hierarchies: [],
    relationships: [],
    glossary: [],
    fact_table: "sales_data",
    grain: "row",
};
test("genere dax template et marque les expressions complexes", () => {
    const generator = new TemplateDaxGenerator();
    const result = generator.generate(model);
    assert.equal(result.measures.find((measure) => measure.name === "Simple")?.origin, "template");
    assert.equal(result.measures.find((measure) => measure.name === "Complex")?.origin, "llm");
});
test("filtre les mesures FK avant generation DAX", () => {
    const generator = new TemplateDaxGenerator();
    const withForeignKeys = {
        ...model,
        measures: [
            ...model.measures,
            {
                name: "Sum Customer Key",
                expression: "SUM(sales_data[CustomerKey])",
                source_columns: [{ table: "sales_data", column: "CustomerKey" }],
            },
        ],
    };
    const result = generator.generate(withForeignKeys);
    assert.equal(result.measures.some((measure) => measure.name === "Sum Customer Key"), false);
});
