import type { SemanticModel } from "../spec/abstract-spec.js";
import type { DAXGenerator, DaxGenerationResult } from "./interfaces.js";
export declare class TemplateDaxGenerator implements DAXGenerator {
    generate(model: SemanticModel): DaxGenerationResult;
}
