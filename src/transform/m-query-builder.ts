import type { MQueryBuilder, MQueryPlan, StarSchemaModel, TransformOp } from "./interfaces.js";

function opToStepExpression(op: TransformOp): string {
  switch (op.type) {
    case "normalize-schema":
      return "Table.TransformColumnTypes(Source, {})";
    case "rename-table":
      return "/* rename table step */ Source";
    case "rename-column":
      return "Table.RenameColumns(Source, {})";
    case "add-filter":
      return "Table.SelectRows(Source, each true)";
    case "create-bridge-table":
      return "Table.NestedJoin(Left, {}, Right, {}, \"Bridge\", JoinKind.Inner)";
    case "add-date-dimension":
      return "List.Dates(#date(2020, 1, 1), 365, #duration(1, 0, 0, 0))";
    default:
      return "Source";
  }
}

export class PowerQueryMBuilder implements MQueryBuilder {
  public build(ops: TransformOp[], schema: StarSchemaModel): MQueryPlan {
    const factQuery = {
      name: schema.factTable,
      steps: [
        { name: "Source", expression: "Sql.Database(\"server\", \"database\")" },
        ...ops.map((op) => ({
          name: `Step_${op.id}`,
          expression: opToStepExpression(op),
        })),
      ],
      final: "Step_op_sys_normalize",
    };

    const dimensionQueries = schema.dimensions.map((dimension) => ({
      name: dimension.name,
      steps: [
        { name: "Source", expression: `Table.SelectColumns(${schema.factTable}, {\"${dimension.keyColumn}\"})` },
      ],
      final: "Source",
    }));

    return {
      queries: [factQuery, ...dimensionQueries],
    };
  }
}
