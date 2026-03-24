import type { AdapterBuildResult, AdapterCapabilities, AdapterDeployResult, AdapterValidationResult, ITargetAdapter } from "./interfaces.js";
import type { AbstractSpec } from "../spec/abstract-spec.js";
export interface PowerBIDeployConfig {
    endpoint?: string;
    apiKey?: string;
}
export declare class PowerBIAdapter implements ITargetAdapter {
    private readonly deployConfig;
    constructor(deployConfig?: PowerBIDeployConfig);
    validate(spec: AbstractSpec): AdapterValidationResult;
    build(spec: AbstractSpec, outputDir: string): Promise<AdapterBuildResult>;
    deploy(buildResult: AdapterBuildResult): Promise<AdapterDeployResult>;
    getCapabilities(): AdapterCapabilities;
}
