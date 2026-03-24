export class LineageQueryServiceImpl {
    lineage;
    constructor(lineage) {
        this.lineage = lineage;
    }
    getTablesForVisual(visualId) {
        const visual = this.lineage.visual_column_map[visualId];
        if (visual === undefined) {
            return [];
        }
        return Array.from(new Set(visual.columns.map((column) => column.table)));
    }
    getJoin(joinId) {
        return this.lineage.joins.find((join) => join.id === joinId);
    }
    getVisualsForColumn(column) {
        const visuals = [];
        for (const [visualId, visual] of Object.entries(this.lineage.visual_column_map)) {
            const found = visual.columns.some((item) => item.table === column.table && item.column === column.column);
            if (found) {
                visuals.push(visualId);
            }
        }
        return visuals;
    }
}
