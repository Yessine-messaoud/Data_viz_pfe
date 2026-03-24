import type { DataLineageSpec, SemanticModel } from "../spec/abstract-spec.js";
import type { TransformationEngine, TransformationEngineResult } from "./interfaces.js";
export declare class DefaultTransformationEngine implements TransformationEngine {
    run(modifications: string[], model: SemanticModel, lineage: DataLineageSpec): TransformationEngineResult;
}
