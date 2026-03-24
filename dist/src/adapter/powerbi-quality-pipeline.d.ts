import AdmZip from "adm-zip";
import type { AbstractSpec } from "../spec/abstract-spec.js";
export interface PowerBIQualityIssue {
    stage: "PBIXValidator" | "ModelValidator" | "DAXValidator";
    code: string;
    message: string;
}
export interface PowerBIQualityWarning {
    stage: "AutoFixer" | "PBIXValidator" | "ModelValidator" | "DAXValidator";
    code: string;
    message: string;
}
export interface PowerBIQualityResult {
    valid: boolean;
    fixedSpec: AbstractSpec;
    issues: PowerBIQualityIssue[];
    warnings: PowerBIQualityWarning[];
}
export declare class PBIXTemplate {
    createBaseArchive(spec: AbstractSpec): AdmZip;
}
export declare class PowerBIQualityPipeline {
    prepareSpec(spec: AbstractSpec): PowerBIQualityResult;
    validatePbix(pbixBytes: Uint8Array): PowerBIQualityIssue[];
}
