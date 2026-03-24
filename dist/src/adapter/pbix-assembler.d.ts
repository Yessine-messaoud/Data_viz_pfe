import type { AbstractSpec } from "../spec/abstract-spec.js";
export interface PBIXAssemblyResult {
    bytes: Uint8Array;
    fileName: string;
}
export declare class PBIXAssembler {
    assemble(spec: AbstractSpec): PBIXAssemblyResult;
}
