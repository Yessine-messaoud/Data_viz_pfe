import type { Driver } from "neo4j-driver";
import type { GraphNode, SemanticGraph, SemanticGraphRepository } from "./interfaces.js";
export declare class Neo4jSemanticGraphRepository implements SemanticGraphRepository {
    private readonly driver;
    constructor(driver: Driver);
    resetGraph(): Promise<void>;
    upsertGraph(graph: SemanticGraph): Promise<void>;
    shortestPath(from: string, to: string): Promise<string[]>;
    detectCycles(): Promise<string[][]>;
    upstreamNodes(nodeId: string): Promise<string[]>;
    private createEdge;
}
export declare function nodeKey(node: GraphNode): string;
