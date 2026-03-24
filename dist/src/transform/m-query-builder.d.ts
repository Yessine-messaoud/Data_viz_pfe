import type { MQueryBuilder, MQueryPlan, StarSchemaModel, TransformOp } from "./interfaces.js";
export declare class PowerQueryMBuilder implements MQueryBuilder {
    build(ops: TransformOp[], schema: StarSchemaModel): MQueryPlan;
}
