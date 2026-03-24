import { XMLParser } from "fast-xml-parser";
import { FederatedDatasourceResolver } from "./federated-datasource-resolver.js";

import type {
  ParsedCalculatedField,
  ParsedDashboard,
  ParsedDatasource,
  ParsedParameter,
  ParsedWorkbook,
  ParsedWorksheet,
  TableauParser,
} from "./interfaces.js";

type JsonRecord = Record<string, unknown>;

function asArray<T>(value: T | T[] | undefined): T[] {
  if (value === undefined) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

function asRecord(value: unknown): JsonRecord | undefined {
  if (typeof value !== "object" || value === null) {
    return undefined;
  }
  return value as JsonRecord;
}

function toTextTokens(value: unknown): string[] {
  if (value === undefined || value === null) {
    return [];
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    const token = String(value).trim();
    return token.length > 0 ? [token] : [];
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => toTextTokens(item));
  }

  const record = asRecord(value);
  if (record === undefined) {
    return [];
  }

  const candidates = ["#text", "name", "field", "column", "value", "caption", "formula"];
  const tokens: string[] = [];
  for (const key of candidates) {
    if (record[key] !== undefined) {
      tokens.push(...toTextTokens(record[key]));
    }
  }

  return tokens;
}

function readTextArray(node: JsonRecord | undefined, key: string): string[] {
  const raw = node?.[key];
  return asArray(raw).flatMap((value) => toTextTokens(value));
}

function assignOptionalString(target: Record<string, unknown>, key: string, value: unknown): void {
  if (value !== undefined) {
    target[key] = String(value);
  }
}

function assignOptionalNumber(target: Record<string, unknown>, key: string, value: unknown): void {
  if (value !== undefined) {
    target[key] = Number(value);
  }
}

function extractWorksheets(root: JsonRecord): ParsedWorksheet[] {
  const worksheetsNode = asRecord(root["worksheets"]);
  const worksheetItems = asArray(worksheetsNode?.["worksheet"]);

  return worksheetItems
    .map((item, index) => asRecord(item))
    .filter((item): item is JsonRecord => item !== undefined)
    .map((worksheet, index) => {
      const tableNode = asRecord(worksheet["table"]);
      const panesNode = asRecord(worksheet["panes"]);
      return {
        id: String(worksheet["name"] ?? `worksheet_${index}`),
        name: String(worksheet["name"] ?? `worksheet_${index}`),
        rows: readTextArray(tableNode, "rows"),
        cols: readTextArray(tableNode, "cols"),
        marks: readTextArray(panesNode, "mark"),
        filters: readTextArray(tableNode, "filter"),
      };
    });
}

function extractDatasources(root: JsonRecord): ParsedDatasource[] {
  const datasourcesNode = asRecord(root["datasources"]);
  const datasourceItems = asArray(datasourcesNode?.["datasource"]);

  return datasourceItems
    .map((item) => asRecord(item))
    .filter((item): item is JsonRecord => item !== undefined)
    .map((datasource, index) => {
      const connectionNode = asRecord(datasource["connection"]);
      const relationItems = asArray(connectionNode?.["relation"]);
      const columnItems = asArray(datasource["column"]);

      const tables = relationItems
        .map((relation) => asRecord(relation))
        .filter((relation): relation is JsonRecord => relation !== undefined)
        .map((relation) => {
          const table: {
            name: string;
            schema?: string;
          } = {
            name: String(relation["table"] ?? relation["name"] ?? "unknown_table"),
          };
          if (relation["schema"] !== undefined) {
            table.schema = String(relation["schema"]);
          }
          return table;
        });

      const columns = columnItems
        .map((column) => asRecord(column))
        .filter((column): column is JsonRecord => column !== undefined)
        .map((column, columnIndex) => {
          const parsedColumn: {
            id: string;
            name: string;
            dataType?: string;
            table?: string;
          } = {
            id: String(column["name"] ?? `column_${columnIndex}`),
            name: String(column["caption"] ?? column["name"] ?? `column_${columnIndex}`),
          };
          if (column["datatype"] !== undefined) {
            parsedColumn.dataType = String(column["datatype"]);
          }
          if (column["table"] !== undefined) {
            parsedColumn.table = String(column["table"]);
          }
          return parsedColumn;
        });

      return {
        id: String(datasource["name"] ?? `datasource_${index}`),
        name: String(datasource["caption"] ?? datasource["name"] ?? `datasource_${index}`),
        tables,
        columns,
      };
    });
}

function extractCalculatedFields(root: JsonRecord): ParsedCalculatedField[] {
  const datasourcesNode = asRecord(root["datasources"]);
  const datasourceItems = asArray(datasourcesNode?.["datasource"]);
  const calculatedFields: ParsedCalculatedField[] = [];

  for (const datasource of datasourceItems) {
    const datasourceNode = asRecord(datasource);
    const columns = asArray(datasourceNode?.["column"]);
    for (const column of columns) {
      const columnNode = asRecord(column);
      const calcNode = asRecord(columnNode?.["calculation"]);
      if (columnNode === undefined || calcNode === undefined) {
        continue;
      }
      calculatedFields.push({
        id: String(columnNode["name"] ?? "calculated_field"),
        name: String(columnNode["caption"] ?? columnNode["name"] ?? "calculated_field"),
        formula: String(calcNode["formula"] ?? ""),
      });
    }
  }

  return calculatedFields;
}

function extractDashboards(root: JsonRecord): ParsedDashboard[] {
  const dashboardsNode = asRecord(root["dashboards"]);
  const dashboardItems = asArray(dashboardsNode?.["dashboard"]);

  return dashboardItems
    .map((item, index) => ({ item: asRecord(item), index }))
    .filter((entry): entry is { item: JsonRecord; index: number } => entry.item !== undefined)
    .map(({ item, index }) => {
      const zonesNode = asRecord(item["zones"]);
      const zonesItems = asArray(zonesNode?.["zone"]);
      const zones = zonesItems
        .map((zone) => asRecord(zone))
        .filter((zone): zone is JsonRecord => zone !== undefined)
        .map((zone, zoneIndex) => {
          const parsedZone: {
            id: string;
            name?: string;
            worksheet?: string;
            type?: string;
            x?: number;
            y?: number;
            w?: number;
            h?: number;
          } = {
            id: String(zone["id"] ?? zone["name"] ?? `zone_${zoneIndex}`),
          };
          assignOptionalString(parsedZone, "name", zone["name"]);
          assignOptionalString(parsedZone, "worksheet", zone["worksheet"]);
          if (zone["type"] !== undefined) {
            parsedZone.type = String(zone["type"]);
          } else if (zone["type-v2"] !== undefined) {
            parsedZone.type = String(zone["type-v2"]);
          }
          if (zone["x"] !== undefined) {
            parsedZone.x = Number(zone["x"]);
          }
          if (zone["y"] !== undefined) {
            parsedZone.y = Number(zone["y"]);
          }
          if (zone["w"] !== undefined) {
            parsedZone.w = Number(zone["w"]);
          }
          if (zone["h"] !== undefined) {
            parsedZone.h = Number(zone["h"]);
          }
          return parsedZone;
        });

      return {
        id: String(item["name"] ?? `dashboard_${index}`),
        name: String(item["name"] ?? `dashboard_${index}`),
        zones,
      };
    });
}

function extractParameters(root: JsonRecord): ParsedParameter[] {
  const datasourcesNode = asRecord(root["datasources"]);
  const datasourceItems = asArray(datasourcesNode?.["datasource"]);
  const parameters: ParsedParameter[] = [];

  for (const datasource of datasourceItems) {
    const datasourceNode = asRecord(datasource);
    const columns = asArray(datasourceNode?.["column"]);
    for (const column of columns) {
      const columnNode = asRecord(column);
      if (columnNode?.["param-domain-type"] === undefined) {
        continue;
      }
      const parameter: {
        id: string;
        name: string;
        dataType?: string;
        currentValue?: string;
      } = {
        id: String(columnNode["name"] ?? "parameter"),
        name: String(columnNode["caption"] ?? columnNode["name"] ?? "parameter"),
      };
      if (columnNode["datatype"] !== undefined) {
        parameter.dataType = String(columnNode["datatype"]);
      }
      if (columnNode["value"] !== undefined) {
        parameter.currentValue = String(columnNode["value"]);
      }
      parameters.push(parameter);
    }
  }

  return parameters;
}

export class XmlTableauParser implements TableauParser {
  private readonly parser: XMLParser;
  private readonly federatedResolver: FederatedDatasourceResolver;

  public constructor() {
    this.parser = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: "",
      trimValues: true,
      processEntities: false,
    });
    this.federatedResolver = new FederatedDatasourceResolver();
  }

  public parseTwbXml(xml: string): ParsedWorkbook {
    const raw = this.parser.parse(xml) as JsonRecord;
    const workbook = asRecord(raw["workbook"]);
    if (workbook === undefined) {
      throw new Error("Invalid TWB content: missing workbook root node");
    }

    const parsed: ParsedWorkbook = {
      worksheets: extractWorksheets(workbook),
      datasources: extractDatasources(workbook),
      calculated_fields: extractCalculatedFields(workbook),
      dashboards: extractDashboards(workbook),
      parameters: extractParameters(workbook),
    };

    return this.federatedResolver.resolve(parsed, workbook);
  }
}
