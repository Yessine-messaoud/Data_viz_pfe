export class Neo4jSemanticGraphRepository {
    driver;
    constructor(driver) {
        this.driver = driver;
    }
    async resetGraph() {
        const session = this.driver.session();
        try {
            await session.run("MATCH (n) DETACH DELETE n");
        }
        finally {
            await session.close();
        }
    }
    async upsertGraph(graph) {
        const session = this.driver.session();
        try {
            for (const node of graph.nodes) {
                await session.run("MERGE (n:SemanticNode {id: $id}) SET n.label = $label, n.weight = $weight, n.metadata = $metadata", {
                    id: node.id,
                    label: node.label,
                    weight: node.weight,
                    metadata: node.metadata ?? {},
                });
            }
            for (const edge of graph.edges) {
                await this.createEdge(session, edge);
            }
        }
        finally {
            await session.close();
        }
    }
    async shortestPath(from, to) {
        const session = this.driver.session();
        try {
            const result = await session.run("MATCH p = shortestPath((a:SemanticNode {id: $from})-[:REL*..10]->(b:SemanticNode {id: $to})) RETURN [n IN nodes(p) | n.id] AS path", { from, to });
            const record = result.records[0];
            if (record === undefined) {
                return [];
            }
            return record.get("path");
        }
        finally {
            await session.close();
        }
    }
    async detectCycles() {
        const session = this.driver.session();
        try {
            const result = await session.run("MATCH p = (n:SemanticNode)-[:REL*1..8]->(n) RETURN [x IN nodes(p) | x.id] AS cycle LIMIT 25");
            return result.records.map((record) => record.get("cycle"));
        }
        finally {
            await session.close();
        }
    }
    async upstreamNodes(nodeId) {
        const session = this.driver.session();
        try {
            const result = await session.run("MATCH p = (up:SemanticNode)-[:REL*1..6]->(target:SemanticNode {id: $id}) RETURN DISTINCT up.id AS id", { id: nodeId });
            return result.records.map((record) => record.get("id"));
        }
        finally {
            await session.close();
        }
    }
    async createEdge(session, edge) {
        await session.run("MATCH (a:SemanticNode {id: $from}), (b:SemanticNode {id: $to}) MERGE (a)-[r:REL {type: $type}]->(b) SET r.weight = $weight", {
            from: edge.from,
            to: edge.to,
            type: edge.type,
            weight: edge.weight,
        });
    }
}
export function nodeKey(node) {
    return `${node.label}:${node.id}`;
}
