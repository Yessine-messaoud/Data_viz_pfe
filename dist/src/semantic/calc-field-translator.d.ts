import type { CalcFieldTranslator } from "./interfaces.js";
export declare class TableauCalcFieldTranslator implements CalcFieldTranslator {
    translateTableauFormula(formula: string): {
        daxExpression: string;
        confidence: number;
        usedLlm: boolean;
    };
}
