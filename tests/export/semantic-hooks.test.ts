import test from "node:test";
import assert from "node:assert/strict";

import { GraphSemanticHooks } from "../../src/export/semantic-hooks.js";
import type { SemanticGraph, SemanticGraphRepository } from "../../src/semantic/interfaces.js";

class HookRepo implements SemanticGraphRepository {
  public async resetGraph(): Promise<void> {}
  public async upsertGraph(_graph: SemanticGraph): Promise<void> {}
  public async shortestPath(_from: string, _to: string): Promise<string[]> {
    return [];
  }
  public async detectCycles(): Promise<string[][]> {
    return [["table:a", "table:b", "table:a"]];
  }
  public async upstreamNodes(nodeId: string): Promise<string[]> {
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
