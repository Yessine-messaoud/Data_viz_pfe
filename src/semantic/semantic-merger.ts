import type { SemanticField, SemanticModel } from "../spec/abstract-spec.js";
import type { SemanticMerger, SemanticMergerInput } from "./interfaces.js";

function applyRenames(fields: SemanticField[], renameMap: Map<string, string>): SemanticField[] {
  return fields.map((field) => {
    const renamed = renameMap.get(field.name) ?? field.name;
    const base: SemanticField = { name: renamed };
    if (field.source !== undefined) {
      base.source = field.source;
    }
    if (field.description !== undefined) {
      base.description = field.description;
    }
    return base;
  });
}

export class HybridSemanticMerger implements SemanticMerger {
  public merge(input: SemanticMergerInput): SemanticModel {
    const renameMap = new Map(input.llm.renamedDimensions.map((rename) => [rename.from, rename.to]));

    // Deterministic structure is preserved; LLM enriches naming and suggestions.
    const dimensions = applyRenames(input.deterministic.dimensions, renameMap).map((dimension) => {
      const description = input.glossaryOverrides[dimension.name] ?? dimension.description;
      const base: SemanticField = {
        name: dimension.name,
      };
      if (dimension.source !== undefined) {
        base.source = dimension.source;
      }
      if (description === undefined) {
        return base;
      }
      return { ...base, description };
    });

    const measures = [
      ...input.deterministic.measures,
      ...input.llm.suggestedMeasures.map((measure) => ({
        name: measure.name,
        expression: measure.expression,
      })),
    ];

    const glossaryMap = new Map<string, string>();
    for (const item of input.deterministic.glossary) {
      glossaryMap.set(item.term, item.definition);
    }
    for (const [term, definition] of Object.entries(input.glossaryOverrides)) {
      glossaryMap.set(term, definition);
    }

    return {
      ...input.deterministic,
      dimensions,
      measures,
      glossary: Array.from(glossaryMap.entries()).map(([term, definition]) => ({ term, definition })),
    };
  }
}
