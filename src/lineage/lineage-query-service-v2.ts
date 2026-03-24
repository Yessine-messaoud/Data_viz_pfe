import type { ColumnRef, JoinDef } from "../spec/abstract-spec.js";
import type { LineageJson, LineageQueryServiceV2 } from "./lineage-spec.js";

export class LineageQueryServiceImpl implements LineageQueryServiceV2 {
  public constructor(private readonly lineage: LineageJson) {}

  public getTablesForVisual(visualId: string): string[] {
    const visual = this.lineage.visual_column_map[visualId];
    if (visual === undefined) {
      return [];
    }
    return Array.from(new Set(visual.columns.map((column) => column.table)));
  }

  public getJoin(joinId: string): JoinDef | undefined {
    return this.lineage.joins.find((join) => join.id === joinId);
  }

  public getVisualsForColumn(column: ColumnRef): string[] {
    const visuals: string[] = [];
    for (const [visualId, visual] of Object.entries(this.lineage.visual_column_map)) {
      const found = visual.columns.some(
        (item) => item.table === column.table && item.column === column.column,
      );
      if (found) {
        visuals.push(visualId);
      }
    }
    return visuals;
  }
}
