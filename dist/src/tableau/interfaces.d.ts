export interface ParsedColumn {
    id: string;
    name: string;
    dataType?: string;
    table?: string;
}
export interface ParsedTable {
    name: string;
    schema?: string;
}
export interface ParsedDatasource {
    id: string;
    name: string;
    tables: ParsedTable[];
    columns: ParsedColumn[];
}
export interface ParsedWorksheet {
    id: string;
    name: string;
    rows: string[];
    cols: string[];
    marks: string[];
    filters: string[];
}
export interface ParsedDashboardZone {
    id: string;
    name?: string;
    worksheet?: string;
    type?: string;
    x?: number;
    y?: number;
    w?: number;
    h?: number;
}
export interface ParsedDashboard {
    id: string;
    name: string;
    zones: ParsedDashboardZone[];
}
export interface ParsedCalculatedField {
    id: string;
    name: string;
    formula: string;
}
export interface ParsedParameter {
    id: string;
    name: string;
    dataType?: string;
    currentValue?: string;
}
export interface ParsedWorkbook {
    worksheets: ParsedWorksheet[];
    datasources: ParsedDatasource[];
    calculated_fields: ParsedCalculatedField[];
    dashboards: ParsedDashboard[];
    parameters: ParsedParameter[];
}
export interface TableauParser {
    parseTwbXml(xml: string): ParsedWorkbook;
}
export interface TwbxExtractionResult {
    twbContent: string;
    twbPath: string;
    dataFiles: Array<{
        path: string;
        type: "hyper" | "csv" | "other";
        bytes: Uint8Array;
    }>;
}
export interface TwbxExtractor {
    extract(buffer: Uint8Array): TwbxExtractionResult;
}
export interface IntentClassification {
    action: string;
    target: "powerbi";
    modifications: string[];
    confidence: number;
}
export interface IntentClassifier {
    classify(request: string): Promise<IntentClassification>;
}
export interface AgentRequestConfig {
    environment: "dev" | "test" | "prod";
    strictMode: boolean;
    flags?: Record<string, boolean>;
}
export interface AgentRequest {
    parsedWorkbook: ParsedWorkbook;
    intent: IntentClassification;
    config: AgentRequestConfig;
}
export interface AgentRequestBuilder {
    build(parsedWorkbook: ParsedWorkbook, intent: IntentClassification, config: AgentRequestConfig): AgentRequest;
}
