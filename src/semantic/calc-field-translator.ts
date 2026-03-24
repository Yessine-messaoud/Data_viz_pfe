import type { CalcFieldTranslator } from "./interfaces.js";

export class TableauCalcFieldTranslator implements CalcFieldTranslator {
  public translateTableauFormula(formula: string): {
    daxExpression: string;
    confidence: number;
    usedLlm: boolean;
  } {
    const normalized = formula.trim().toLowerCase();
    const simpleSum = formula.trim().match(/^sum\(([^()]+)\)$/i);
    const simpleAvg = formula.trim().match(/^avg\(([^()]+)\)$/i);
    const simpleCountd = formula.trim().match(/^countd\(([^()]+)\)$/i);

    if (simpleSum?.[1] !== undefined) {
      const inside = simpleSum[1].trim();
      return {
        daxExpression: `SUM(${inside})`,
        confidence: 0.95,
        usedLlm: false,
      };
    }

    if (simpleAvg?.[1] !== undefined) {
      const inside = simpleAvg[1].trim();
      return {
        daxExpression: `AVERAGE(${inside})`,
        confidence: 0.95,
        usedLlm: false,
      };
    }

    if (simpleCountd?.[1] !== undefined) {
      const inside = simpleCountd[1].trim();
      return {
        daxExpression: `DISTINCTCOUNT(${inside})`,
        confidence: 0.95,
        usedLlm: false,
      };
    }

    if (/\bcountd\s*\(/i.test(formula)) {
      return {
        daxExpression: formula.replace(/\bcountd\s*\(/gi, "DISTINCTCOUNT("),
        confidence: 0.85,
        usedLlm: false,
      };
    }

    // LOD and table calculations are delegated to LLM branch.
    return {
      daxExpression: `/* LLM_TRANSLATION_REQUIRED */ ${formula}`,
      confidence: 0.55,
      usedLlm: true,
    };
  }
}
