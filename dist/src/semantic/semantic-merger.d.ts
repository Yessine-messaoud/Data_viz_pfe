import type { SemanticModel } from "../spec/abstract-spec.js";
import type { SemanticMerger, SemanticMergerInput } from "./interfaces.js";
export declare class HybridSemanticMerger implements SemanticMerger {
    merge(input: SemanticMergerInput): SemanticModel;
}
