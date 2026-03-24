import type { AbstractSpec } from "./abstract-spec.js";
export interface AbstractSpecValidationIssue {
    code: "UNKNOWN_TABLE" | "RAW_FEDERATED_TOKEN" | "EMPTY_VISUAL_BINDING";
    message: string;
    path: string;
}
export interface AbstractSpecValidationReport {
    valid: boolean;
    issueCount: number;
    issues: AbstractSpecValidationIssue[];
}
export declare class AbstractSpecValidator {
    validate(spec: AbstractSpec): AbstractSpecValidationReport;
}
