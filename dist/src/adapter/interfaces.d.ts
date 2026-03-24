import type { AbstractSpec } from "../spec/abstract-spec.js";
export interface AdapterCapabilities {
    target: string;
    supportsDeploy: boolean;
    supportsValidation: boolean;
    artifactTypes: string[];
}
export interface AdapterValidationResult {
    valid: boolean;
    errors: string[];
    warnings: string[];
}
export interface AdapterBuildResult {
    artifactPath: string;
    artifactBytes: Uint8Array;
    metadata: Record<string, string | number | boolean>;
}
export interface AdapterDeployResult {
    success: boolean;
    url?: string;
    message?: string;
}
export interface ITargetAdapter {
    validate(spec: AbstractSpec): AdapterValidationResult;
    build(spec: AbstractSpec, outputDir: string): Promise<AdapterBuildResult>;
    deploy(buildResult: AdapterBuildResult): Promise<AdapterDeployResult>;
    getCapabilities(): AdapterCapabilities;
}
