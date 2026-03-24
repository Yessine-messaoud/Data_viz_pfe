function columnId(column) {
    return `column:${column.table}.${column.column}`;
}
export class AdditiveSemanticGraphBuilder {
    repository;
    constructor(repository) {
        this.repository = repository;
    }
    async build(model, lineage) {
        const nodes = [];
        const edges = [];
        const graphTables = lineage.full_tables ?? lineage.tables;
        for (const table of graphTables) {
            nodes.push({
                id: `table:${table.name}`,
                label: "table",
                weight: 1,
            });
        }
        for (const usage of lineage.columns_used) {
            nodes.push({
                id: columnId(usage.column),
                label: "column",
                weight: usage.usage === "measure" ? 0.9 : 0.7,
            });
            edges.push({
                from: `table:${usage.column.table}`,
                to: columnId(usage.column),
                type: "has_column",
                weight: 1,
            });
            edges.push({
                from: `visual:${usage.visual_id}`,
                to: columnId(usage.column),
                type: "uses",
                weight: 1,
            });
        }
        for (const join of lineage.joins) {
            edges.push({
                from: `table:${join.left_table}`,
                to: `table:${join.right_table}`,
                type: "joins",
                weight: 1,
            });
            edges.push({
                from: `table:${join.right_table}`,
                to: `table:${join.left_table}`,
                type: "joins",
                weight: 1,
            });
        }
        for (const measure of model.measures) {
            nodes.push({
                id: `measure:${measure.name}`,
                label: "measure",
                weight: 1,
            });
            for (const sourceColumn of measure.source_columns ?? []) {
                edges.push({
                    from: `measure:${measure.name}`,
                    to: columnId(sourceColumn),
                    type: "depends_on",
                    weight: 1,
                });
            }
        }
        for (const [visualId, visualLineage] of Object.entries(lineage.visual_column_map)) {
            nodes.push({
                id: `visual:${visualId}`,
                label: "visual",
                weight: 1,
            });
            for (const filter of visualLineage.filters) {
                edges.push({
                    from: `visual:${visualId}`,
                    to: columnId(filter.column),
                    type: "filters",
                    weight: 0.8,
                });
            }
        }
        const graph = deduplicateGraph({ nodes, edges });
        await this.repository.resetGraph();
        await this.repository.upsertGraph(graph);
        return graph;
    }
}
function deduplicateGraph(graph) {
    const nodeMap = new Map();
    for (const node of graph.nodes) {
        if (!nodeMap.has(node.id)) {
            nodeMap.set(node.id, node);
        }
    }
    const edgeMap = new Map();
    for (const edge of graph.edges) {
        const key = `${edge.from}|${edge.type}|${edge.to}`;
        if (!edgeMap.has(key)) {
            edgeMap.set(key, edge);
        }
    }
    return {
        nodes: Array.from(nodeMap.values()),
        edges: Array.from(edgeMap.values()),
    };
}
