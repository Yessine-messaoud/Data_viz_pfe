import test from "node:test";
import assert from "node:assert/strict";
import { HybridSemanticMerger } from "../../src/semantic/semantic-merger.js";
const deterministic = {
    entities: [],
    measures: [{ name: "Sales", expression: "SUM([Sales])" }],
    dimensions: [{ name: "CA" }],
    hierarchies: [],
    relationships: [],
    glossary: [{ term: "CA", definition: "Old" }],
    fact_table: "fact_sales",
    grain: "line",
};
test("le merger preserve la structure et enrichit semantiquement", () => {
    const merger = new HybridSemanticMerger();
    const merged = merger.merge({
        deterministic,
        llm: {
            renamedDimensions: [{ from: "CA", to: "Chiffre d'Affaires", confidence: 0.9 }],
            suggestedMeasures: [{ name: "GMV", expression: "SUM([GMV])", confidence: 0.8 }],
            disambiguationNotes: [],
        },
        glossaryOverrides: { "Chiffre d'Affaires": "Metric business" },
    });
    assert.equal(merged.dimensions[0]?.name, "Chiffre d'Affaires");
    assert.equal(merged.measures.length, 2);
});
