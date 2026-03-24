import test from "node:test";
import assert from "node:assert/strict";

import { AdditiveSemanticGraphBuilder } from "../../src/semantic/semantic-graph-builder.js";
import type { DataLineageSpec, SemanticModel } from "../../src/spec/abstract-spec.js";
import type { SemanticGraph, SemanticGraphRepository } from "../../src/semantic/interfaces.js";

class InMemoryRepo implements SemanticGraphRepository {
  public graph: SemanticGraph = { nodes: [], edges: [] };

  public async resetGraph(): Promise<void> {
    this.graph = { nodes: [], edges: [] };
  }

  public async upsertGraph(graph: SemanticGraph): Promise<void> {
    this.graph = graph;
  }

  public async shortestPath(_from: string, _to: string): Promise<string[]> {
    return [];
  }

  public async detectCycles(): Promise<string[][]> {
    return [];
  }

  public async upstreamNodes(_nodeId: string): Promise<string[]> {
    return [];
  }
}

const model: SemanticModel = {
  entities: [],
  measures: [{ name: "Total Sales", expression: "SUM([Sales])", source_columns: [{ table: "fact_sales", column: "sales_amount" }] }],
  dimensions: [],
  hierarchies: [],
  relationships: [],
  glossary: [],
  fact_table: "fact_sales",
  grain: "line",
};

const lineage: DataLineageSpec = {
  tables: [{ id: "t1", name: "fact_sales" }],
  joins: [],
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
      joins_used: [],
      filters: [],
    },
  },
};

test("build graphe additif depuis semantic model + lineage", async () => {
  const repo = new InMemoryRepo();
  const builder = new AdditiveSemanticGraphBuilder(repo);
  const graph = await builder.build(model, lineage);

  assert.ok(graph.nodes.find((n) => n.id === "table:fact_sales"));
  assert.ok(graph.nodes.find((n) => n.id === "visual:v1"));
  assert.ok(graph.edges.find((e) => e.type === "uses"));
  assert.equal(repo.graph.nodes.length, graph.nodes.length);
});
