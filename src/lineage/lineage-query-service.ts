import type { ColumnRef, DataLineageSpec, JoinDef } from "../spec/abstract-spec.js";
import type { LineageQueryService, SemanticGraphRepository } from "../semantic/interfaces.js";

function columnNodeId(column: ColumnRef): string {
  return `column:${column.table}.${column.column}`;
}

export class GraphBackedLineageQueryService implements LineageQueryService {
  public constructor(
    private readonly lineage: DataLineageSpec,
    private readonly graphRepository: SemanticGraphRepository,
  ) {}

  public async getTablesForVisual(visualId: string): Promise<string[]> {
    const upstream = await this.graphRepository.upstreamNodes(`visual:${visualId}`);
    return upstream.filter((nodeId) => nodeId.startsWith("table:")).map((nodeId) => nodeId.replace("table:", ""));
  }

  public getJoin(joinId: string): JoinDef | undefined {
    return this.lineage.joins.find((join) => join.id === joinId);
  }

  public async getVisualsForColumn(column: ColumnRef): Promise<string[]> {
    const paths = await this.graphRepository.upstreamNodes(columnNodeId(column));
    return paths.filter((nodeId) => nodeId.startsWith("visual:")).map((nodeId) => nodeId.replace("visual:", ""));
  }

  public async getPathBetweenColumns(from: ColumnRef, to: ColumnRef): Promise<string[]> {
    return this.graphRepository.shortestPath(columnNodeId(from), columnNodeId(to));
  }
}
