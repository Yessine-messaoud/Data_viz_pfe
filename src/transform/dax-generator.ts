import type { SemanticModel } from "../spec/abstract-spec.js";
import type { DAXGenerator, DaxGenerationResult } from "./interfaces.js";

function isComplexExpression(expression: string): boolean {
  const lower = expression.toLowerCase();
  return lower.includes("fixed") || lower.includes("table") || lower.includes("window") || lower.includes("running");
}

function isForeignKeyMeasure(modelMeasure: SemanticModel["measures"][number]): boolean {
  const name = modelMeasure.name.trim();
  const expression = modelMeasure.expression;
  const sourceColumns = modelMeasure.source_columns ?? [];
  const fkPattern = /(?:key|_key|keyid|_id|id|linekey)$/i;

  if (fkPattern.test(name.replace(/^sum\s+/i, ""))) {
    return true;
  }

  if (/SUM\s*\([^)]*(?:Key|_Key|KeyID|_id|ID|LineKey)\]?\)/i.test(expression)) {
    return true;
  }

  return sourceColumns.some((column) => fkPattern.test(column.column));
}

export class TemplateDaxGenerator implements DAXGenerator {
  public generate(model: SemanticModel): DaxGenerationResult {
    const measures = model.measures.filter((measure) => !isForeignKeyMeasure(measure)).map((measure) => {
      if (isComplexExpression(measure.expression)) {
        return {
          name: measure.name,
          expression: `/* LLM_REQUIRED */ ${measure.expression}`,
          origin: "llm" as const,
        };
      }

      return {
        name: measure.name,
        expression: measure.expression,
        origin: "template" as const,
      };
    });

    return { measures };
  }
}
