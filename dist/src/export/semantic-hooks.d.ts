import type { VisualLineage } from "../spec/abstract-spec.js";
import type { SemanticGraphRepository, SemanticHooks } from "../semantic/interfaces.js";
export declare class GraphSemanticHooks implements SemanticHooks {
    private readonly repository;
    constructor(repository: SemanticGraphRepository);
    analyzeImpact(changedNodeIds: string[]): Promise<Record<string, string[]>>;
    validateNoCyclesBeforePbixAssembly(): Promise<{
        valid: boolean;
        cycles: string[][];
    }>;
    buildLlmContextForComplexCalc(calcExpression: string, visualLineage: VisualLineage): Promise<string>;
}
