import type { VisualLineage } from "../spec/abstract-spec.js";
import type { SemanticGraphRepository, SemanticHooks } from "../semantic/interfaces.js";

export class GraphSemanticHooks implements SemanticHooks {
  public constructor(private readonly repository: SemanticGraphRepository) {}

  public async analyzeImpact(changedNodeIds: string[]): Promise<Record<string, string[]>> {
    const impacted: Record<string, string[]> = {};
    for (const nodeId of changedNodeIds) {
      impacted[nodeId] = await this.repository.upstreamNodes(nodeId);
    }
    return impacted;
  }

  public async validateNoCyclesBeforePbixAssembly(): Promise<{ valid: boolean; cycles: string[][] }> {
    const cycles = await this.repository.detectCycles();
    return {
      valid: cycles.length === 0,
      cycles,
    };
  }

  public async buildLlmContextForComplexCalc(calcExpression: string, visualLineage: VisualLineage): Promise<string> {
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
