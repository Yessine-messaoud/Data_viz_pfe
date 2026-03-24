import type { AbstractSpec, BuildIntent, DataLineageSpec, SemanticModel, WorkbookInput } from "./abstract-spec.js";
declare function toCanonicalJson(value: unknown): string;
declare function hashSha256(data: string | Uint8Array): string;
declare function toUuidFromSha256(sha256Hex: string): string;
export declare class AbstractSpecBuilder {
    build(workbook: WorkbookInput, intent: BuildIntent, semantic_model: SemanticModel, lineage: DataLineageSpec): AbstractSpec;
}
export { toCanonicalJson, hashSha256, toUuidFromSha256 };
