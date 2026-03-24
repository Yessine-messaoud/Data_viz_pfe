import type { TransformOp, TransformPlanner } from "./interfaces.js";
export declare class IntentTransformPlanner implements TransformPlanner {
    plan(modifications: string[]): TransformOp[];
}
