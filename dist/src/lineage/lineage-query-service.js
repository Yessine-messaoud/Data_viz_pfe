function columnNodeId(column) {
    return `column:${column.table}.${column.column}`;
}
export class GraphBackedLineageQueryService {
    lineage;
    graphRepository;
    constructor(lineage, graphRepository) {
        this.lineage = lineage;
        this.graphRepository = graphRepository;
    }
    async getTablesForVisual(visualId) {
        const upstream = await this.graphRepository.upstreamNodes(`visual:${visualId}`);
        return upstream.filter((nodeId) => nodeId.startsWith("table:")).map((nodeId) => nodeId.replace("table:", ""));
    }
    getJoin(joinId) {
        return this.lineage.joins.find((join) => join.id === joinId);
    }
    async getVisualsForColumn(column) {
        const paths = await this.graphRepository.upstreamNodes(columnNodeId(column));
        return paths.filter((nodeId) => nodeId.startsWith("visual:")).map((nodeId) => nodeId.replace("visual:", ""));
    }
    async getPathBetweenColumns(from, to) {
        return this.graphRepository.shortestPath(columnNodeId(from), columnNodeId(to));
    }
}
