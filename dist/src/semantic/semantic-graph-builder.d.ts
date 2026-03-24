import type { DataLineageSpec, SemanticModel } from "../spec/abstract-spec.js";
import type { SemanticGraph, SemanticGraphBuilder, SemanticGraphRepository } from "./interfaces.js";
export declare class AdditiveSemanticGraphBuilder implements SemanticGraphBuilder {
    private readonly repository;
    constructor(repository: SemanticGraphRepository);
    build(model: SemanticModel, lineage: DataLineageSpec): Promise<SemanticGraph>;
}
