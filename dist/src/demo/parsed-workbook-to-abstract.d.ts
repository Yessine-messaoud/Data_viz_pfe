import type { AbstractSpec, DashboardSpec, JoinDef, DataLineageSpec, SemanticModel } from "../spec/abstract-spec.js";
import type { ParsedWorkbook, TwbxExtractionResult } from "../tableau/interfaces.js";
type SampleRow = Record<string, string | number | boolean | null>;
interface SourceTableColumn {
    name: string;
    type: string;
}
interface SourceTableProfile {
    table_name: string;
    columns: SourceTableColumn[];
    sample_data: SampleRow[];
    source: "xml" | "csv" | "hyper";
}
export declare function inferFactTableFromSourceTables(sourceTables: SourceTableProfile[], joins: JoinDef[]): string;
export declare function buildDashboardSpecFromParsedWorkbook(parsedWorkbook: ParsedWorkbook): DashboardSpec;
export declare function buildSemanticModelFromParsedWorkbook(parsedWorkbook: ParsedWorkbook): SemanticModel;
export declare function buildLineageFromParsedWorkbook(parsedWorkbook: ParsedWorkbook, dashboardSpec: DashboardSpec): DataLineageSpec;
export interface SemanticLayerOutput {
    dashboard_spec: DashboardSpec;
    semantic_model: SemanticModel;
    data_lineage: DataLineageSpec;
    logs: string[];
    warnings: string[];
}
export declare function validateDaxExpressionForRetry(expression: string): {
    valid: boolean;
    reason?: string;
};
export interface CloudTranslationContext {
    formula: string;
    parsedWorkbook: ParsedWorkbook;
    existingMeasures: string[];
    previousError?: string;
}
export type GroqTranslationContext = CloudTranslationContext;
export declare function buildCloudCalcMessages(context: CloudTranslationContext): Array<{
    role: "system" | "user";
    content: string;
}>;
export declare const buildGroqCalcMessages: typeof buildCloudCalcMessages;
export declare function parsedWorkbookToTableColumns(parsedWorkbook: ParsedWorkbook): Record<string, string[]>;
export declare function runSemanticLayerFromParsedWorkbook(parsedWorkbook: ParsedWorkbook, extraction?: TwbxExtractionResult): SemanticLayerOutput;
export declare function runSemanticLayerFromParsedWorkbookHybrid(parsedWorkbook: ParsedWorkbook, extraction?: TwbxExtractionResult): Promise<SemanticLayerOutput>;
export declare function buildAbstractSpecPivot(semanticLayer: SemanticLayerOutput, workbookRaw: string | Uint8Array, workbookName: string): AbstractSpec;
export declare function createAbstractSpecFromParsedWorkbook(parsedWorkbook: ParsedWorkbook, workbookRaw: string | Uint8Array, workbookName: string, extraction?: TwbxExtractionResult): AbstractSpec;
export declare function createAbstractSpecFromParsedWorkbookHybrid(parsedWorkbook: ParsedWorkbook, workbookRaw: string | Uint8Array, workbookName: string, extraction?: TwbxExtractionResult): Promise<AbstractSpec>;
export {};
