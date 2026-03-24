import type { AbstractSpec } from "../spec/abstract-spec.js";
import type { LineageJson } from "../lineage/lineage-spec.js";
export interface VizAgentRunOutput {
    artifact: string;
    spec: AbstractSpec;
    lineage: LineageJson;
    url?: string;
}
export interface VizAgentRunOptions {
    artifactTarget?: "pbix" | "rdl";
}
export declare class VizAgentCore {
    run(workbookPath: string, workspaceRoot: string, options?: VizAgentRunOptions): Promise<VizAgentRunOutput>;
    private loadWorkbook;
}
