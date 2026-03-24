import test from "node:test";
import assert from "node:assert/strict";
import { HybridSemanticEnricher } from "../../src/semantic/semantic-enricher.js";
const baseModel = {
    entities: [],
    measures: [],
    dimensions: [{ name: "CA" }],
    hierarchies: [],
    relationships: [],
    glossary: [],
    fact_table: "fact_sales",
    grain: "line",
};
test("enrichissement semantique ajoute renommage et suggestions", async () => {
    const enricher = new HybridSemanticEnricher();
    const result = await enricher.enrich(baseModel, {
        glossary: { CA: "Chiffre d'Affaires" },
        ambiguousColumns: [{ table: "fact_sales", column: "amount" }],
        complexCalcs: ["{ FIXED [Customer]: SUM([Sales]) }"],
    });
    assert.equal(result.renamedDimensions[0]?.to, "Chiffre d'Affaires");
    assert.equal(result.suggestedMeasures.length, 1);
});
test("enrichissement semantique peut utiliser un endpoint Groq compatible", async () => {
    const mockFetch = (async () => new Response(JSON.stringify({
        choices: [
            {
                message: {
                    content: JSON.stringify({
                        renamedDimensions: [{ from: "CA", to: "Revenue", confidence: 0.98 }],
                        suggestedMeasures: [{ name: "Gross Margin", expression: "DIVIDE([Profit],[Sales])", confidence: 0.91 }],
                        disambiguationNotes: ["Resolved CA semantic naming."],
                    }),
                },
            },
        ],
    }), { status: 200, headers: { "content-type": "application/json" } }));
    const enricher = new HybridSemanticEnricher({
        apiKey: "test-key",
        fetchImpl: mockFetch,
    });
    const result = await enricher.enrich(baseModel, {
        glossary: { CA: "Chiffre d'Affaires" },
        ambiguousColumns: [{ table: "fact_sales", column: "amount" }],
        complexCalcs: ["{ FIXED [Customer]: SUM([Sales]) }"],
    });
    assert.equal(result.renamedDimensions[0]?.to, "Revenue");
    assert.equal(result.suggestedMeasures[0]?.name, "Gross Margin");
});
