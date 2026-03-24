import type { AbstractSpec } from "../spec/abstract-spec.js";
export interface SqlServerRdlConfig {
    server: string;
    database: string;
    integratedSecurity?: boolean;
    username?: string;
    password?: string;
    datasetName?: string;
    queryTop?: number;
    query?: string;
    fields?: Array<{
        fieldName: string;
        sourceColumn: string;
    }>;
}
export interface PaginatedRdlBuildOptions {
    mode?: "local" | "sqlserver";
    sqlServer?: SqlServerRdlConfig;
}
export interface PaginatedRdlConstraint {
    id: string;
    description: string;
    requiredPattern: RegExp;
}
export declare const PAGINATED_RDL_CONSTRAINTS: PaginatedRdlConstraint[];
export declare function validatePaginatedRdl(xml: string, mode?: "local" | "sqlserver"): string[];
export interface RdlShapeValidationIssue {
    code: string;
    message: string;
}
export interface RdlShapeValidationReport {
    valid: boolean;
    mode: "local" | "sqlserver";
    strictMode: boolean;
    issues: RdlShapeValidationIssue[];
}
export interface RdlBusinessConstraints {
    requiredDatasetNames?: string[];
    requiredSections?: string[];
    datasetNamePattern?: RegExp | string;
    textboxNamePattern?: RegExp | string;
    tablixNamePattern?: RegExp | string;
}
export interface RdlValidationOptions {
    strictMode?: boolean;
    businessConstraints?: RdlBusinessConstraints;
}
export declare function validateGeneratedRdlShape(xml: string, mode?: "local" | "sqlserver", options?: RdlValidationOptions): RdlShapeValidationReport;
export declare function buildPaginatedRdl(spec: AbstractSpec, options?: PaginatedRdlBuildOptions): string;
export declare function writePaginatedRdl(spec: AbstractSpec, outputDir: string, validationOptions?: RdlValidationOptions): Promise<string>;
export declare function writePaginatedRdlSqlServer(spec: AbstractSpec, outputDir: string, config: SqlServerRdlConfig, validationOptions?: RdlValidationOptions): Promise<string>;
