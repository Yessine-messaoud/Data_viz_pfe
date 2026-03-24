import type { ColumnRef, DataLineageSpec, ExportManifest, SemanticModel } from "../spec/abstract-spec.js";

export type TransformOpType =
  | "rename-column"
  | "rename-table"
  | "add-filter"
  | "add-date-dimension"
  | "create-bridge-table"
  | "normalize-schema"
  | "custom";

export interface TransformOp {
  id: string;
  order: number;
  type: TransformOpType;
  payload: Record<string, string | number | boolean>;
  source: "intent" | "system";
}

export interface TransformPlanner {
  plan(modifications: string[]): TransformOp[];
}

export interface StarDimensionTable {
  name: string;
  keyColumn: string;
  sourceColumns: ColumnRef[];
}

export interface StarBridgeTable {
  name: string;
  leftDimension: string;
  rightDimension: string;
}

export interface StarSchemaModel {
  factTable: string;
  dimensions: StarDimensionTable[];
  bridges: StarBridgeTable[];
  hasAutoDateDimension: boolean;
}

export interface StarSchemaBuilder {
  build(model: SemanticModel, lineage: DataLineageSpec): StarSchemaModel;
}

export interface MStep {
  name: string;
  expression: string;
}

export interface MQueryPlan {
  queries: Array<{
    name: string;
    steps: MStep[];
    final: string;
  }>;
}

export interface MQueryBuilder {
  build(ops: TransformOp[], schema: StarSchemaModel): MQueryPlan;
}

export interface DaxGenerationResult {
  measures: Array<{
    name: string;
    expression: string;
    origin: "template" | "llm";
  }>;
}

export interface DAXGenerator {
  generate(model: SemanticModel): DaxGenerationResult;
}

export interface TransformationEngineResult {
  ops: TransformOp[];
  schema: StarSchemaModel;
  mPlan: MQueryPlan;
  dax: DaxGenerationResult;
  exportManifest: ExportManifest;
}

export interface TransformationEngine {
  run(modifications: string[], model: SemanticModel, lineage: DataLineageSpec): TransformationEngineResult;
}
