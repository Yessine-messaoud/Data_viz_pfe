import type { ColumnRef, DataLineageSpec, JoinDef } from "../spec/abstract-spec.js";
import type { LineageQueryService, SemanticGraphRepository } from "../semantic/interfaces.js";
export declare class GraphBackedLineageQueryService implements LineageQueryService {
    private readonly lineage;
    private readonly graphRepository;
    constructor(lineage: DataLineageSpec, graphRepository: SemanticGraphRepository);
    getTablesForVisual(visualId: string): Promise<string[]>;
    getJoin(joinId: string): JoinDef | undefined;
    getVisualsForColumn(column: ColumnRef): Promise<string[]>;
    getPathBetweenColumns(from: ColumnRef, to: ColumnRef): Promise<string[]>;
}
