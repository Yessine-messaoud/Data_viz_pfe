import type { ColumnRef, JoinDef } from "../spec/abstract-spec.js";
import type { LineageJson, LineageQueryServiceV2 } from "./lineage-spec.js";
export declare class LineageQueryServiceImpl implements LineageQueryServiceV2 {
    private readonly lineage;
    constructor(lineage: LineageJson);
    getTablesForVisual(visualId: string): string[];
    getJoin(joinId: string): JoinDef | undefined;
    getVisualsForColumn(column: ColumnRef): string[];
}
