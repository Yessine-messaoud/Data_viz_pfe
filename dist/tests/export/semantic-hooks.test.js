import test from "node:test";
import assert from "node:assert/strict";
import { GraphSemanticHooks } from "../../src/export/semantic-hooks.js";
class HookRepo {
    async resetGraph() { }
    async upsertGraph(_graph) { }
    async shortestPath(_from, _to) {
        return [];
    }
    async detectCycles() {
        return [["table:a", "table:b", "table:a"]];
    }
    async upstreamNodes(nodeId) {
        return [`impact:${nodeId}`];
    }
}
test("hooks impact analysis + cycle validation + contexte LLM", async () => {
    const hooks = new GraphSemanticHooks(new HookRepo());
    const impact = await hooks.analyzeImpact(["column:fact_sales.sales_amount"]);
    assert.deepEqual(impact["column:fact_sales.sales_amount"], ["impact:column:fact_sales.sales_amount"]);
    const validation = await hooks.validateNoCyclesBeforePbixAssembly();
    assert.equal(validation.valid, false);
    assert.equal(validation.cycles.length, 1);
    const context = await hooks.buildLlmContextForComplexCalc("{ FIXED [Region]: SUM([Sales]) }", {
        columns: [{ table: "fact_sales", column: "sales_amount" }],
        joins_used: ["j1"],
        filters: [],
    });
    assert.match(context, /Complex Calc Context/);
});
