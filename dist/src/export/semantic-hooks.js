export class GraphSemanticHooks {
    repository;
    constructor(repository) {
        this.repository = repository;
    }
    async analyzeImpact(changedNodeIds) {
        const impacted = {};
        for (const nodeId of changedNodeIds) {
            impacted[nodeId] = await this.repository.upstreamNodes(nodeId);
        }
        return impacted;
    }
    async validateNoCyclesBeforePbixAssembly() {
        const cycles = await this.repository.detectCycles();
        return {
            valid: cycles.length === 0,
            cycles,
        };
    }
    async buildLlmContextForComplexCalc(calcExpression, visualLineage) {
        const firstColumn = visualLineage.columns[0];
        const baseNode = firstColumn ? `column:${firstColumn.table}.${firstColumn.column}` : "";
        const neighbors = baseNode.length > 0 ? await this.repository.upstreamNodes(baseNode) : [];
        return [
            "Complex Calc Context",
            `Expression: ${calcExpression}`,
            `Lineage Columns: ${visualLineage.columns.map((c) => `${c.table}.${c.column}`).join(", ")}`,
            `Joins Used: ${visualLineage.joins_used.join(", ")}`,
            `Upstream Semantic Nodes: ${neighbors.join(", ")}`,
        ].join("\n");
    }
}
