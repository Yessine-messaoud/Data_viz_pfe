import type { DataLineageSpec, SemanticModel } from "../spec/abstract-spec.js";
import type { StarSchemaBuilder, StarSchemaModel } from "./interfaces.js";
export declare class SemanticStarSchemaBuilder implements StarSchemaBuilder {
    build(model: SemanticModel, lineage: DataLineageSpec): StarSchemaModel;
}
