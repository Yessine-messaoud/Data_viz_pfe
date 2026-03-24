import type { DataLineageSpec, ExportManifest, SemanticModel } from "../spec/abstract-spec.js";
import { TemplateDaxGenerator } from "./dax-generator.js";
import type { TransformationEngine, TransformationEngineResult } from "./interfaces.js";
import { PowerQueryMBuilder } from "./m-query-builder.js";
import { SemanticStarSchemaBuilder } from "./star-schema-builder.js";
import { IntentTransformPlanner } from "./transform-planner.js";

function toMIdentifier(name: string): string {
  const trimmed = name.trim();
  if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(trimmed)) {
    return trimmed;
  }
  return `#"${trimmed.replace(/"/g, '""')}"`;
}

function toMStringLiteral(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

function toMValue(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return "null";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "null";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return toMStringLiteral(value);
}

function toMType(type: string): string {
  const normalized = type.trim().toLowerCase();
  if (["integer", "int", "real", "float", "double", "number", "numeric", "decimal"].includes(normalized)) {
    return "number";
  }
  if (["bool", "boolean", "logical"].includes(normalized)) {
    return "logical";
  }
  if (normalized.includes("date") || normalized.includes("time")) {
    return "datetime";
  }
  return "text";
}

function buildDatasetMQuery(
  tableName: string,
  profile?: {
    columns: Array<{ name: string; type: string }>;
    sample_data: Array<Record<string, string | number | boolean | null>>;
  },
  sampledRows?: Array<Record<string, string | number | boolean | null>>,
): string {
  const columns = profile?.columns ?? [];
  const rows = profile?.sample_data ?? sampledRows ?? [];

  if (columns.length === 0) {
    return `let\n  Source = #table(type table [table_name = text], {{${toMStringLiteral(tableName)}}})\nin\n  Source`;
  }

  const tableType = columns.map((column) => `${toMIdentifier(column.name)} = ${toMType(column.type)}`).join(", ");
  const rowValues = rows
    .slice(0, 5)
    .map((row) => {
      const ordered = columns.map((column) => toMValue(row[column.name]));
      return `{${ordered.join(", ")}}`;
    })
    .join(",\n    ");

  const dataRows = rowValues.length > 0 ? rowValues : "";

  return `let\n  Source = #table(\n    type table [${tableType}],\n    {${dataRows.length > 0 ? `\n    ${dataRows}\n    ` : ""}}\n  )\nin\n  Source`;
}

export class DefaultTransformationEngine implements TransformationEngine {
  public run(modifications: string[], model: SemanticModel, lineage: DataLineageSpec): TransformationEngineResult {
    const planner = new IntentTransformPlanner();
    const schemaBuilder = new SemanticStarSchemaBuilder();
    const mBuilder = new PowerQueryMBuilder();
    const daxGenerator = new TemplateDaxGenerator();

    const ops = planner.plan(modifications);
    const schema = schemaBuilder.build(model, lineage);
    const mPlan = mBuilder.build(ops, schema);
    const dax = daxGenerator.generate(model);

    const fullTables = lineage.full_tables ?? lineage.tables;
    const profilesByTable = new Map(
      (lineage.full_table_profiles ?? []).map((profile) => [profile.table_name.toLowerCase(), profile]),
    );
    const sampledRows = lineage.sampled_rows ?? {};

    const datasetQueries = fullTables.map((table) => {
      const safeName = table.name.replace(/[^a-zA-Z0-9_]/g, "_");
      const profile = profilesByTable.get(table.name.toLowerCase());
      return {
        name: `Dataset_${safeName}`,
        query: buildDatasetMQuery(table.name, profile, sampledRows[table.name]),
      };
    });

    const plannedQueries = mPlan.queries.map((query) => ({
      name: query.name,
      query: query.steps.map((step) => `${step.name} = ${step.expression}`).join("\n"),
    }));

    const dedup = new Map<string, { name: string; query: string }>();
    for (const query of [...plannedQueries, ...datasetQueries]) {
      dedup.set(query.name, query);
    }

    const exportManifest: ExportManifest = {
      target: "powerbi",
      model_config: {
        dataset_name: `${schema.factTable}_dataset`,
      },
      dax_measures: dax.measures.map((measure) => ({
        name: measure.name,
        expression: measure.expression,
      })),
      m_queries: Array.from(dedup.values()),
      post_export_hooks: [],
    };

    return {
      ops,
      schema,
      mPlan,
      dax,
      exportManifest,
    };
  }
}
