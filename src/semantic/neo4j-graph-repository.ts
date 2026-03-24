import type { Driver } from "neo4j-driver";

import type { GraphEdge, GraphNode, SemanticGraph, SemanticGraphRepository } from "./interfaces.js";

export class Neo4jSemanticGraphRepository implements SemanticGraphRepository {
  public constructor(private readonly driver: Driver) {}

  public async resetGraph(): Promise<void> {
    const session = this.driver.session();
    try {
      await session.run("MATCH (n) DETACH DELETE n");
    } finally {
      await session.close();
    }
  }

  public async upsertGraph(graph: SemanticGraph): Promise<void> {
    const session = this.driver.session();
    try {
      for (const node of graph.nodes) {
        await session.run(
          "MERGE (n:SemanticNode {id: $id}) SET n.label = $label, n.weight = $weight, n.metadata = $metadata",
          {
            id: node.id,
            label: node.label,
            weight: node.weight,
            metadata: node.metadata ?? {},
          },
        );
      }

      for (const edge of graph.edges) {
        await this.createEdge(session, edge);
      }
    } finally {
      await session.close();
    }
  }

  public async shortestPath(from: string, to: string): Promise<string[]> {
    const session = this.driver.session();
    try {
      const result = await session.run(
        "MATCH p = shortestPath((a:SemanticNode {id: $from})-[:REL*..10]->(b:SemanticNode {id: $to})) RETURN [n IN nodes(p) | n.id] AS path",
        { from, to },
      );
      const record = result.records[0];
      if (record === undefined) {
        return [];
      }
      return record.get("path") as string[];
    } finally {
      await session.close();
    }
  }

  public async detectCycles(): Promise<string[][]> {
    const session = this.driver.session();
    try {
      const result = await session.run(
        "MATCH p = (n:SemanticNode)-[:REL*1..8]->(n) RETURN [x IN nodes(p) | x.id] AS cycle LIMIT 25",
      );
      return result.records.map((record) => record.get("cycle") as string[]);
    } finally {
      await session.close();
    }
  }

  public async upstreamNodes(nodeId: string): Promise<string[]> {
    const session = this.driver.session();
    try {
      const result = await session.run(
        "MATCH p = (up:SemanticNode)-[:REL*1..6]->(target:SemanticNode {id: $id}) RETURN DISTINCT up.id AS id",
        { id: nodeId },
      );
      return result.records.map((record) => record.get("id") as string);
    } finally {
      await session.close();
    }
  }

  private async createEdge(
    session: { run: (query: string, params?: Record<string, unknown>) => Promise<unknown> },
    edge: GraphEdge,
  ): Promise<void> {
    await session.run(
      "MATCH (a:SemanticNode {id: $from}), (b:SemanticNode {id: $to}) MERGE (a)-[r:REL {type: $type}]->(b) SET r.weight = $weight",
      {
        from: edge.from,
        to: edge.to,
        type: edge.type,
        weight: edge.weight,
      },
    );
  }
}

export function nodeKey(node: GraphNode): string {
  return `${node.label}:${node.id}`;
}
