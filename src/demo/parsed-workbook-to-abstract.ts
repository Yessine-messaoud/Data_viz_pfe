import { AbstractSpecBuilder } from "../spec/abstract-spec-builder.js";
import type {
  AbstractSpec,
  ColumnRef,
  DashboardPage,
  DashboardSpec,
  JoinDef,
  DataLineageSpec,
  RelationshipDef,
  SemanticModel,
  VisualSpec,
  VisualType,
} from "../spec/abstract-spec.js";
import type { ParsedJoinInput } from "../semantic/interfaces.js";
import { TableauCalcFieldTranslator } from "../semantic/calc-field-translator.js";
import type { SemanticEnrichmentContext } from "../semantic/interfaces.js";
import { TableauJoinResolver } from "../semantic/join-resolver.js";
import { HybridSemanticEnricher } from "../semantic/semantic-enricher.js";
import { HybridSemanticMerger } from "../semantic/semantic-merger.js";
import { DefaultSchemaMapper } from "../semantic/schema-mapper.js";
import { readHyperTablesFromBytes } from "../tableau/hyper-api-reader.js";
import type { ParsedWorkbook, ParsedWorksheet, TwbxExtractionResult } from "../tableau/interfaces.js";

const NUMERIC_TYPES = new Set(["integer", "int", "real", "float", "double", "number", "numeric", "decimal"]);
const FACT_KEY_PATTERN = /(?:key|_key|keyid|_id|id|linekey)$/i;
const BUSINESS_MEASURE_NAME_PATTERN = /(amount|qty|quantity|price|cost|sales|profit|revenue|margin)/i;
const FK_MEASURE_PATTERN = /(?:key|_key|keyid|_id|id|linekey)$/i;
const MEASURE_NAMES_TOKEN = /^:?measure names$/i;

const KPI_WORKSHEET_MEASURE_MAP: Record<string, string[]> = {
  CD_KPIs: ["Sum Total Sales", "Sum Profit", "Sum # Sales Orders", "Sum Avg. Sales per Customer"],
  PD_KPIs: ["Sum Total Sales", "Sum Profit", "Sum # Sales Orders", "Sum Avg. Sales per Customer"],
  SO_KPIs: ["Sum Total Sales", "Sum Profit", "Sum # Sales Orders", "Sum Avg. Sales per Customer"],
};

type SampleRow = Record<string, string | number | boolean | null>;

interface SourceTableColumn {
  name: string;
  type: string;
}

interface SourceTableProfile {
  table_name: string;
  columns: SourceTableColumn[];
  sample_data: SampleRow[];
  source: "xml" | "csv" | "hyper";
}

interface SourceExtractionDiagnostics {
  logs: string[];
  warnings: string[];
}

interface SourceTableExtractionResult {
  tables: SourceTableProfile[];
  diagnostics: SourceExtractionDiagnostics;
}

function sanitizeToken(value: string): string {
  return value.replace(/\[/g, "").replace(/\]/g, "").trim();
}

function parseResolvedToken(token: string): ColumnRef | undefined {
  const clean = sanitizeToken(token);

  const aggMatch = clean.match(/^[a-z]+\(([^.]+)\.(.+)\)$/i);
  if (aggMatch?.[1] !== undefined && aggMatch[2] !== undefined) {
    return {
      table: sanitizeToken(aggMatch[1]),
      column: sanitizeToken(aggMatch[2]),
    };
  }

  const dotIndex = clean.indexOf(".");
  if (dotIndex > 0 && dotIndex < clean.length - 1) {
    return {
      table: clean.slice(0, dotIndex),
      column: clean.slice(dotIndex + 1),
    };
  }

  return undefined;
}

function inferColumnRef(token: string, parsedWorkbook: ParsedWorkbook): ColumnRef {
  const clean = sanitizeToken(token);
  const resolved = parseResolvedToken(clean);
  if (resolved !== undefined) {
    return resolved;
  }

  const firstDatasource = parsedWorkbook.datasources[0];
  const fallbackTable = firstDatasource?.tables[0]?.name ?? "unknown_table";

  for (const datasource of parsedWorkbook.datasources) {
    for (const column of datasource.columns) {
      const candidates = [column.id, column.name].map((candidate) => sanitizeToken(candidate));
      if (candidates.includes(clean)) {
        return {
          table: column.table ?? fallbackTable,
          column: clean,
        };
      }
    }
  }

  return {
    table: fallbackTable,
    column: clean,
  };
}

function inferVisualType(worksheet: ParsedWorksheet, mapper: DefaultSchemaMapper): VisualType {
  const name = worksheet.name.toLowerCase();

  if (name.includes("kpis")) {
    return "card";
  }
  if (name.includes("salesbymonth") || name.includes("sales vs profit")) {
    return "lineChart";
  }
  if (name.includes("salesbycountry") || name.includes("salescountry")) {
    return "filledMap";
  }
  if (
    name.includes("salesbyprod") ||
    name.includes("salesproduct") ||
    name.includes("topprod") ||
    name.includes("topcustomers") ||
    name.includes("topproduct") ||
    name.includes("topbycity")
  ) {
    return "barChart";
  }
  if (name.includes("matrix")) {
    return "tableEx";
  }

  const mark = worksheet.marks[0] ?? "";
  const mapped = mapper.mapVisualType(mark);
  if (mapped === "line") {
    return "lineChart";
  }
  if (mapped === "bar") {
    return "barChart";
  }
  if (mapped === "map") {
    return "filledMap";
  }
  if (mapped === "table") {
    return "tableEx";
  }
  if (mapped === "card") {
    return "card";
  }
  return "tableEx";
}

function isMeasureNamesToken(token?: string): boolean {
  if (token === undefined) {
    return false;
  }
  return MEASURE_NAMES_TOKEN.test(sanitizeToken(token));
}

function hasMeasureNamesPlaceholder(worksheet: ParsedWorksheet): boolean {
  const tokens = [...worksheet.rows, ...worksheet.cols, ...worksheet.filters];
  return tokens.some((token) => isMeasureNamesToken(token));
}

function scoreFactTable(
  table: SourceTableProfile,
  joins: JoinDef[],
): { fk: number; joinMany: number; measure: number; total: number } {
  const fk = table.columns.filter((column) => FACT_KEY_PATTERN.test(normalizeColumnName(column.name))).length;
  const joinMany = joins.filter((join) => normalizeTableName(join.left_table) === normalizeTableName(table.table_name)).length;
  const measure = table.columns.filter((column) => {
    const colType = column.type.toLowerCase();
    const colName = normalizeColumnName(column.name);
    return NUMERIC_TYPES.has(colType) && BUSINESS_MEASURE_NAME_PATTERN.test(colName);
  }).length;

  return {
    fk,
    joinMany,
    measure,
    total: fk * 3 + joinMany * 2 + measure,
  };
}

export function inferFactTableFromSourceTables(sourceTables: SourceTableProfile[], joins: JoinDef[]): string {
  const ranked = sourceTables
    .map((table) => ({
      tableName: table.table_name,
      score: scoreFactTable(table, joins),
    }))
    .sort((left, right) => {
      if (right.score.total !== left.score.total) {
        return right.score.total - left.score.total;
      }
      if (right.score.fk !== left.score.fk) {
        return right.score.fk - left.score.fk;
      }
      if (right.score.measure !== left.score.measure) {
        return right.score.measure - left.score.measure;
      }
      return left.tableName.localeCompare(right.tableName);
    });

  return ranked[0]?.tableName ?? "unknown_fact";
}

function normalizeColumnName(name: string): string {
  return sanitizeToken(name).trim().toLowerCase();
}

function pickFallbackAxisColumns(parsedWorkbook: ParsedWorkbook): {
  fallbackX?: ColumnRef;
  fallbackY?: ColumnRef;
} {
  const allColumns = parsedWorkbook.datasources.flatMap((datasource) => datasource.columns);
  const firstDatasource = parsedWorkbook.datasources[0];
  const fallbackTable = firstDatasource?.tables[0]?.name ?? "unknown_table";

  const dimensionCandidate = allColumns.find(
    (column) => !NUMERIC_TYPES.has((column.dataType ?? "").toLowerCase()),
  );
  const measureCandidate = allColumns.find((column) => NUMERIC_TYPES.has((column.dataType ?? "").toLowerCase()));

  const result: {
    fallbackX?: ColumnRef;
    fallbackY?: ColumnRef;
  } = {};

  if (dimensionCandidate !== undefined) {
    result.fallbackX = {
      table: dimensionCandidate.table ?? fallbackTable,
      column: sanitizeToken(dimensionCandidate.name),
    };
  }

  if (measureCandidate !== undefined) {
    result.fallbackY = {
      table: measureCandidate.table ?? fallbackTable,
      column: sanitizeToken(measureCandidate.name),
    };
  }

  return result;
}

function extractFormulaSources(formula: string, parsedWorkbook: ParsedWorkbook): ColumnRef[] {
  const bracketTokens = Array.from(formula.matchAll(/\[([^\]]+)\]/g)).map((match) => match[1] ?? "");
  const resolved = bracketTokens
    .map((token) => token.trim())
    .filter((token) => token.length > 0)
    .map((token) => inferColumnRef(token, parsedWorkbook));

  const unique = new Map<string, ColumnRef>();
  for (const ref of resolved) {
    unique.set(`${normalizeTableName(ref.table)}.${normalizeColumnName(ref.column)}`, ref);
  }

  return Array.from(unique.values());
}

function inferJoinsFromSourceTables(sourceTables: SourceTableProfile[]): JoinDef[] {
  const parsedJoinInputs: ParsedJoinInput[] = [];

  for (let leftIndex = 0; leftIndex < sourceTables.length; leftIndex += 1) {
    const left = sourceTables[leftIndex];
    if (left === undefined) {
      continue;
    }

    const leftColumns = new Map(
      left.columns.map((column) => [normalizeColumnName(column.name), sanitizeToken(column.name)]),
    );

    for (let rightIndex = leftIndex + 1; rightIndex < sourceTables.length; rightIndex += 1) {
      const right = sourceTables[rightIndex];
      if (right === undefined) {
        continue;
      }

      const rightColumns = new Map(
        right.columns.map((column) => [normalizeColumnName(column.name), sanitizeToken(column.name)]),
      );

      const sharedKeys = Array.from(leftColumns.keys()).filter((column) => rightColumns.has(column));
      if (sharedKeys.length === 0) {
        continue;
      }

      const rankedKey =
        sharedKeys.find((column) => /(^id$|_id$|id$|_key$|key$)/.test(column)) ?? sharedKeys[0] ?? "";
      if (rankedKey.length === 0) {
        continue;
      }

      const leftColumn = leftColumns.get(rankedKey);
      const rightColumn = rightColumns.get(rankedKey);
      if (leftColumn === undefined || rightColumn === undefined) {
        continue;
      }

      parsedJoinInputs.push({
        id: `join_${leftIndex + 1}_${rightIndex + 1}`,
        leftTable: left.table_name,
        rightTable: right.table_name,
        joinType: "inner",
        keys: [{ leftColumn, rightColumn }],
      });
    }
  }

  const resolver = new TableauJoinResolver();
  return resolver.resolve(parsedJoinInputs);
}

function buildRelationshipsFromJoins(joins: JoinDef[]): RelationshipDef[] {
  const relationships: RelationshipDef[] = [];
  for (const join of joins) {
    const key = join.keys[0];
    if (key === undefined) {
      continue;
    }
    relationships.push({
      from: key.left,
      to: key.right,
      cardinality: "many-to-one",
      cross_filter_direction: "single",
    });
  }
  return relationships;
}

function normalizeTableName(name: string): string {
  return name.trim().toLowerCase();
}

function parseCsvPreview(bytes: Uint8Array): { columns: SourceTableColumn[]; sampleData: SampleRow[] } {
  const text = Buffer.from(bytes).toString("utf8");
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) {
    return { columns: [], sampleData: [] };
  }

  const headers = lines[0]?.split(",").map((header) => header.trim()) ?? [];
  const columns = headers.map((name) => ({ name, type: "string" }));
  const sampleData: SampleRow[] = [];

  for (const line of lines.slice(1, 6)) {
    const values = line.split(",").map((value) => value.trim());
    const row: SampleRow = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    sampleData.push(row);
  }

  return { columns, sampleData };
}

function parseBinaryHeadPreview(bytes: Uint8Array): SampleRow[] {
  const result: SampleRow[] = [];
  const head = Array.from(bytes.slice(0, 5));
  head.forEach((value, index) => {
    result.push({
      _byte_index: index + 1,
      _binary_byte_hex: `0x${value.toString(16).padStart(2, "0")}`,
    });
  });
  return result;
}

function extractSourceTables(
  parsedWorkbook: ParsedWorkbook,
  extraction?: TwbxExtractionResult,
): SourceTableExtractionResult {
  const diagnostics: SourceExtractionDiagnostics = {
    logs: [],
    warnings: [],
  };

  const profiles = new Map<string, SourceTableProfile>();

  for (const datasource of parsedWorkbook.datasources) {
    for (const table of datasource.tables) {
      const key = normalizeTableName(table.name);
      const columns = datasource.columns
        .filter((column) => normalizeTableName(column.table ?? "") === key)
        .map((column) => ({ name: sanitizeToken(column.name), type: column.dataType ?? "unknown" }));

      if (!profiles.has(key)) {
        profiles.set(key, {
          table_name: table.name,
          columns,
          sample_data: [],
          source: "xml",
        });
      } else {
        const current = profiles.get(key);
        if (current !== undefined && current.columns.length === 0 && columns.length > 0) {
          current.columns = columns;
        }
      }
    }
  }

  if (extraction !== undefined) {
    for (const file of extraction.dataFiles) {
      const fileName = file.path.split(/[\\/]/).pop() ?? file.path;
      const tableName = fileName.replace(/\.[^.]+$/, "");
      const key = normalizeTableName(tableName);

      const existing = profiles.get(key);
      if (file.type === "csv") {
        const parsed = parseCsvPreview(file.bytes);
        const profile: SourceTableProfile = existing ?? {
          table_name: tableName,
          columns: [],
          sample_data: [],
          source: "csv",
        };
        if (profile.columns.length === 0 && parsed.columns.length > 0) {
          profile.columns = parsed.columns;
        }
        if (profile.sample_data.length === 0 && parsed.sampleData.length > 0) {
          profile.sample_data = parsed.sampleData;
        }
        profile.source = "csv";
        profiles.set(key, profile);
      } else if (file.type === "hyper") {
        const hyperRead = readHyperTablesFromBytes(file.bytes, file.path);
        diagnostics.logs.push(...hyperRead.logs);
        diagnostics.warnings.push(...hyperRead.warnings);

        if (hyperRead.tables.length > 0) {
          for (const tableProfile of hyperRead.tables) {
            const hyperKey = normalizeTableName(tableProfile.table_name);
            const current = profiles.get(hyperKey);
            if (current === undefined) {
              profiles.set(hyperKey, {
                table_name: tableProfile.table_name,
                columns: tableProfile.columns,
                sample_data: tableProfile.sample_data,
                source: "hyper",
              });
            } else {
              if (current.columns.length === 0) {
                current.columns = tableProfile.columns;
              }
              if (current.sample_data.length === 0) {
                current.sample_data = tableProfile.sample_data;
              }
              current.source = "hyper";
            }
          }
        } else {
          const profile: SourceTableProfile = existing ?? {
            table_name: tableName,
            columns: [],
            sample_data: [],
            source: "hyper",
          };

          if (profile.columns.length === 0) {
            profile.columns = [
              { name: "_byte_index", type: "integer" },
              { name: "_binary_byte_hex", type: "string" },
            ];
          }
          if (profile.sample_data.length === 0) {
            profile.sample_data = parseBinaryHeadPreview(file.bytes);
          }
          profile.source = "hyper";
          profiles.set(key, profile);
        }
      }
    }
  }

  const tables = Array.from(profiles.values());

  diagnostics.logs.push(`tables detected: ${tables.length}`);
  for (const table of tables) {
    diagnostics.logs.push(
      `table ${table.table_name}: columns=${table.columns.length}, source=${table.source}, preview_rows=${table.sample_data.length}`,
    );
    if (table.sample_data.length === 0) {
      diagnostics.warnings.push(`WARN_NO_SAMPLE_DATA:${table.table_name}`);
    }
  }

  if (tables.length === 0) {
    throw new Error("No tables detected from Tableau datasource (hyper/xml).");
  }

  return { tables, diagnostics };
}

function findMissingVisualColumns(
  dashboardSpec: DashboardSpec,
  sourceTables: SourceTableProfile[],
): string[] {
  const tableColumns = new Set<string>();
  for (const table of sourceTables) {
    for (const column of table.columns) {
      tableColumns.add(`${normalizeTableName(table.table_name)}.${normalizeTableName(column.name)}`);
    }
  }

  const missing: string[] = [];
  for (const page of dashboardSpec.pages) {
    for (const visual of page.visuals) {
      const axisRefs = [
        visual.data_binding.axes.x,
        visual.data_binding.axes.y,
        visual.data_binding.axes.color,
        visual.data_binding.axes.size,
        visual.data_binding.axes.tooltip,
      ].filter((ref): ref is ColumnRef => ref !== undefined);

      for (const ref of axisRefs) {
        const key = `${normalizeTableName(ref.table)}.${normalizeTableName(ref.column)}`;
        if (!tableColumns.has(key)) {
          missing.push(`WARN_VISUAL_COLUMN_NOT_FOUND:${visual.id}:${ref.table}.${ref.column}`);
        }
      }
    }
  }

  return missing;
}

export function buildDashboardSpecFromParsedWorkbook(parsedWorkbook: ParsedWorkbook): DashboardSpec {
  const mapper = new DefaultSchemaMapper();
  const { fallbackX, fallbackY } = pickFallbackAxisColumns(parsedWorkbook);

  const worksheetVisuals = new Map<string, VisualSpec[]>();
  let visualCounter = 0;

  for (const worksheet of parsedWorkbook.worksheets) {
    const xToken = worksheet.cols[0] ?? worksheet.filters[0];
    const yToken = worksheet.rows[0] ?? worksheet.cols[1];
    const colorToken = worksheet.cols[1] ?? worksheet.rows[1];
    const sizeToken = worksheet.rows[1] ?? worksheet.cols[2];
    const tooltipToken = worksheet.filters[0] ?? worksheet.cols[2] ?? worksheet.rows[2];

    const baseAxes: VisualSpec["data_binding"]["axes"] = {};
    if (xToken !== undefined && !isMeasureNamesToken(xToken)) {
      baseAxes.x = inferColumnRef(xToken, parsedWorkbook);
    } else if (fallbackX !== undefined) {
      baseAxes.x = fallbackX;
    }
    if (yToken !== undefined && !isMeasureNamesToken(yToken)) {
      baseAxes.y = inferColumnRef(yToken, parsedWorkbook);
    } else if (fallbackY !== undefined) {
      baseAxes.y = fallbackY;
    }
    if (colorToken !== undefined && !isMeasureNamesToken(colorToken)) {
      baseAxes.color = inferColumnRef(colorToken, parsedWorkbook);
    }
    if (sizeToken !== undefined && !isMeasureNamesToken(sizeToken)) {
      baseAxes.size = inferColumnRef(sizeToken, parsedWorkbook);
    }
    if (tooltipToken !== undefined && !isMeasureNamesToken(tooltipToken)) {
      baseAxes.tooltip = inferColumnRef(tooltipToken, parsedWorkbook);
    }

    const visualsForWorksheet: VisualSpec[] = [];
    const measureNamesDetected = hasMeasureNamesPlaceholder(worksheet);
    const kpiMeasures = KPI_WORKSHEET_MEASURE_MAP[worksheet.name] ?? [];

    if (measureNamesDetected && kpiMeasures.length > 0) {
      for (const measureName of kpiMeasures) {
        visualCounter += 1;
        visualsForWorksheet.push({
          id: `visual_${visualCounter}`,
          source_worksheet: worksheet.name,
          type: "card",
          position: {
            row: visualCounter - 1,
            column: 0,
            row_span: 1,
            column_span: 1,
          },
          data_binding: {
            axes: {
              ...(baseAxes.x !== undefined ? { x: baseAxes.x } : {}),
              ...(baseAxes.y !== undefined ? { y: baseAxes.y } : {}),
              ...(baseAxes.tooltip !== undefined ? { tooltip: baseAxes.tooltip } : {}),
            },
          },
          title: `${worksheet.name} - ${measureName}`,
        });
      }
    } else {
      visualCounter += 1;
      visualsForWorksheet.push({
        id: `visual_${visualCounter}`,
        source_worksheet: worksheet.name,
        type: inferVisualType(worksheet, mapper),
        position: {
          row: visualCounter - 1,
          column: 0,
          row_span: 1,
          column_span: 1,
        },
        data_binding: {
          axes: baseAxes,
        },
        title: worksheet.name,
      });
    }

    worksheetVisuals.set(worksheet.name, visualsForWorksheet);
  }

  const worksheetNameSet = new Set(parsedWorkbook.worksheets.map((worksheet) => worksheet.name));
  const pageByPrefix: Record<string, string> = {
    CD_: "customer details",
    PD_: "product details",
    SO_: "sales overview",
  };

  const resolveWorksheetsForDashboard = (dashboardName: string): string[] => {
    const dashboard = parsedWorkbook.dashboards.find((entry) => entry.name === dashboardName);
    if (dashboard === undefined) {
      return [];
    }

    const fromZones = dashboard.zones
      .flatMap((zone) => [zone.worksheet, zone.name])
      .filter((name): name is string => name !== undefined)
      .filter((name) => worksheetNameSet.has(name));

    if (fromZones.length > 0) {
      return Array.from(new Set(fromZones));
    }

    const normalizedDashboard = dashboard.name.trim().toLowerCase();
    const matchingPrefix = Object.entries(pageByPrefix).find(([, page]) => page === normalizedDashboard)?.[0];
    if (matchingPrefix !== undefined) {
      return parsedWorkbook.worksheets
        .map((worksheet) => worksheet.name)
        .filter((worksheetName) => worksheetName.startsWith(matchingPrefix));
    }

    return [];
  };

  let pages: DashboardPage[];
  if (parsedWorkbook.dashboards.length > 0) {
    pages = parsedWorkbook.dashboards.map((dashboard) => {
      const dashboardWorksheets = resolveWorksheetsForDashboard(dashboard.name);
      const resolvedWorksheets =
        dashboardWorksheets.length > 0
          ? dashboardWorksheets
          : parsedWorkbook.worksheets.map((worksheet) => worksheet.name);
      const visuals = resolvedWorksheets.flatMap((worksheetName) => worksheetVisuals.get(worksheetName) ?? []);

      return {
        id: dashboard.id,
        name: dashboard.name,
        visuals,
      };
    });
  } else {
    pages = [
      {
        id: "page_1",
        name: "Worksheet Page",
        visuals: Array.from(worksheetVisuals.values()).flatMap((visuals) => visuals),
      },
    ];
  }

  return {
    pages,
    global_filters: [],
    theme: {
      name: "tableau-imported",
      palette: ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
    },
    refresh_policy: {
      mode: "manual",
    },
  };
}

export function buildSemanticModelFromParsedWorkbook(parsedWorkbook: ParsedWorkbook): SemanticModel {
  const allColumns = parsedWorkbook.datasources.flatMap((datasource) => datasource.columns);
  const calcTranslator = new TableauCalcFieldTranslator();

  const dimensions = allColumns
    .filter((column) => !NUMERIC_TYPES.has((column.dataType ?? "").toLowerCase()))
    .map((column) => ({
      name: sanitizeToken(column.name),
      source: {
        table: column.table ?? parsedWorkbook.datasources[0]?.tables[0]?.name ?? "unknown_table",
        column: sanitizeToken(column.name),
      },
    }));

  const measures = allColumns
    .filter((column) => NUMERIC_TYPES.has((column.dataType ?? "").toLowerCase()))
    .map((column) => {
      const sourceTable = column.table ?? parsedWorkbook.datasources[0]?.tables[0]?.name ?? "unknown_table";
      const sourceColumn = sanitizeToken(column.name);
      return {
        name: `Sum ${sourceColumn}`,
        expression: `SUM(${sourceTable}[${sourceColumn}])`,
        source_columns: [
          {
            table: sourceTable,
            column: sourceColumn,
          },
        ],
      };
    });

  const calcMeasures = parsedWorkbook.calculated_fields.map((field) => {
    const translated = calcTranslator.translateTableauFormula(field.formula);
    const sourceColumns = extractFormulaSources(field.formula, parsedWorkbook);

    return {
      name: sanitizeToken(field.name),
      expression: translated.daxExpression,
      ...(sourceColumns.length > 0 ? { source_columns: sourceColumns } : {}),
      ...(translated.usedLlm ? { format_string: "LLM_TRANSLATION_REQUIRED" } : {}),
    };
  });

  const semanticMeasures = [...measures, ...calcMeasures];

  const glossary = [
    ...parsedWorkbook.calculated_fields.map((field) => ({
      term: field.name,
      definition: field.formula,
    })),
    ...calcMeasures
      .filter((measure) => measure.format_string === "LLM_TRANSLATION_REQUIRED")
      .map((measure) => ({
        term: `${measure.name} (translation)`,
        definition: `DAX generated with low confidence: ${measure.expression}`,
      })),
  ];

  return {
    entities: parsedWorkbook.datasources.map((datasource) => ({
      name: datasource.name,
    })),
    measures: semanticMeasures,
    dimensions,
    hierarchies: [],
    relationships: [],
    glossary,
    fact_table: parsedWorkbook.datasources[0]?.tables[0]?.name ?? "unknown_fact",
    grain: "inferred from worksheet rows",
  };
}

export function buildLineageFromParsedWorkbook(
  parsedWorkbook: ParsedWorkbook,
  dashboardSpec: DashboardSpec,
): DataLineageSpec {
  const tables = parsedWorkbook.datasources.flatMap((datasource, index) =>
    datasource.tables.map((table, tableIndex) => ({
      id: `table_${index + 1}_${tableIndex + 1}`,
      name: table.name,
      ...(table.schema !== undefined ? { schema: table.schema } : {}),
    })),
  );

  const visuals = dashboardSpec.pages.flatMap((page) => page.visuals);

  const columns_used = visuals.flatMap((visual) => {
    const usages: DataLineageSpec["columns_used"] = [];
    if (visual.data_binding.axes.x !== undefined) {
      usages.push({ visual_id: visual.id, column: visual.data_binding.axes.x, usage: "axis" });
    }
    if (visual.data_binding.axes.y !== undefined) {
      usages.push({ visual_id: visual.id, column: visual.data_binding.axes.y, usage: "measure" });
    }
    if (visual.data_binding.axes.tooltip !== undefined) {
      usages.push({ visual_id: visual.id, column: visual.data_binding.axes.tooltip, usage: "tooltip" });
    }
    return usages;
  });

  const visual_column_map: DataLineageSpec["visual_column_map"] = {};
  for (const visual of visuals) {
    const cols: ColumnRef[] = [];
    if (visual.data_binding.axes.x !== undefined) {
      cols.push(visual.data_binding.axes.x);
    }
    if (visual.data_binding.axes.y !== undefined) {
      cols.push(visual.data_binding.axes.y);
    }
    if (visual.data_binding.axes.tooltip !== undefined) {
      cols.push(visual.data_binding.axes.tooltip);
    }
    visual_column_map[visual.id] = {
      columns: cols,
      joins_used: [],
      filters: [],
    };
  }

  return {
    tables,
    joins: [],
    columns_used,
    visual_column_map,
  };
}

export interface SemanticLayerOutput {
  dashboard_spec: DashboardSpec;
  semantic_model: SemanticModel;
  data_lineage: DataLineageSpec;
  logs: string[];
  warnings: string[];
}

function isComplexCalcFormula(formula: string): boolean {
  return /\b(fixed|window|running|countd|if|case)\b/i.test(formula);
}

function buildSemanticEnrichmentContext(
  parsedWorkbook: ParsedWorkbook,
  model: SemanticModel,
  lineage: DataLineageSpec,
): SemanticEnrichmentContext {
  const glossary: Record<string, string> = Object.fromEntries(
    model.glossary
      .filter((entry) => entry.term.trim().length > 0 && entry.definition.trim().length > 0)
      .map((entry) => [entry.term, entry.definition]),
  );

  const byColumnName = new Map<string, Set<string>>();
  for (const usage of lineage.columns_used) {
    const key = normalizeColumnName(usage.column.column);
    const tables = byColumnName.get(key) ?? new Set<string>();
    tables.add(normalizeTableName(usage.column.table));
    byColumnName.set(key, tables);
  }

  const ambiguousColumns = lineage.columns_used
    .map((usage) => usage.column)
    .filter((column, index, list) => {
      const tables = byColumnName.get(normalizeColumnName(column.column));
      if ((tables?.size ?? 0) <= 1) {
        return false;
      }
      const key = `${normalizeTableName(column.table)}.${normalizeColumnName(column.column)}`;
      return list.findIndex((item) => `${normalizeTableName(item.table)}.${normalizeColumnName(item.column)}` === key) === index;
    });

  const complexCalcs = parsedWorkbook.calculated_fields
    .map((field) => field.formula)
    .filter((formula) => isComplexCalcFormula(formula));

  return {
    glossary,
    ambiguousColumns,
    complexCalcs,
  };
}

function sanitizeMistralDaxExpression(expression: string): string {
  const normalized = expression
    .replace(/\bcountd\s*\(/gi, "DISTINCTCOUNT(")
    .replace(/\bavg\s*\(/gi, "AVERAGE(")
    .replace(/\s+/g, " ");
  return normalized.trim().length > 0 ? normalized : "0";
}

const KNOWN_DAX_FUNCTIONS = new Set([
  "SUM",
  "AVERAGE",
  "MIN",
  "MAX",
  "COUNT",
  "COUNTROWS",
  "DISTINCTCOUNT",
  "CALCULATE",
  "FILTER",
  "DIVIDE",
  "IF",
  "SWITCH",
  "RELATED",
  "RELATEDTABLE",
  "ALL",
  "VALUES",
  "DATEADD",
  "TOTALYTD",
]);

function hasBalancedParentheses(expression: string): boolean {
  let balance = 0;
  for (const char of expression) {
    if (char === "(") {
      balance += 1;
    }
    if (char === ")") {
      balance -= 1;
      if (balance < 0) {
        return false;
      }
    }
  }
  return balance === 0;
}

export function validateDaxExpressionForRetry(expression: string): { valid: boolean; reason?: string } {
  const normalized = expression.trim();
  if (normalized.length === 0) {
    return { valid: false, reason: "empty_expression" };
  }
  if (!hasBalancedParentheses(normalized)) {
    return { valid: false, reason: "unbalanced_parentheses" };
  }
  if (/\b[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*\b/.test(normalized)) {
    return { valid: false, reason: "dot_notation_detected" };
  }

  const functions = Array.from(normalized.toUpperCase().matchAll(/\b([A-Z][A-Z0-9_]*)\(/g)).map((match) => match[1]);
  for (const fn of functions) {
    if (fn !== undefined && !KNOWN_DAX_FUNCTIONS.has(fn)) {
      return { valid: false, reason: `unknown_function:${fn}` };
    }
  }

  return { valid: true };
}

function resolveMistralApiKey(): string {
  const envKey = process.env.MISTRAL_API_KEY?.trim();
  if (envKey !== undefined && envKey.length > 0) {
    return envKey;
  }

  // Backward compatibility with previous provider variable.
  const legacyKey = process.env.GROQ_API_KEY?.trim();
  if (legacyKey !== undefined && legacyKey.length > 0) {
    return legacyKey;
  }

  return "";
}

function resolveMistralModel(): string {
  return process.env.MISTRAL_MODEL?.trim() || "mistral-small-latest";
}

function resolveMistralBaseUrl(): string {
  return process.env.MISTRAL_BASE_URL?.trim() || "https://api.mistral.ai/v1";
}

function resolveCloudApiKey(): string {
  const mistralKey = resolveMistralApiKey();
  if (mistralKey.length > 0) {
    return mistralKey;
  }

  // Kept for compatibility only.
  const envKey = process.env.GROQ_API_KEY?.trim();
  if (envKey !== undefined && envKey.length > 0) {
    return envKey;
  }
  return "";
}

function resolveLocalLlamaEndpoint(): string {
  return process.env.LOCAL_LLM_BASE_URL?.trim() || "http://127.0.0.1:11434";
}

function resolveLocalLlamaModel(): string {
  return process.env.LOCAL_LLM_MODEL?.trim() || "llama3";
}

export interface CloudTranslationContext {
  formula: string;
  parsedWorkbook: ParsedWorkbook;
  existingMeasures: string[];
  previousError?: string;
}

// Backward-compatible alias for previous provider naming.
export type GroqTranslationContext = CloudTranslationContext;

export function buildCloudCalcMessages(
  context: CloudTranslationContext,
): Array<{ role: "system" | "user"; content: string }> {
  const tableColumns = parsedWorkbookToTableColumns(context.parsedWorkbook);
  const fewShotExamples = [
    {
      tableau: "SUM([Sales Amount])",
      dax: "SUM(sales_data[Sales Amount])",
    },
    {
      tableau: "COUNTD([Sales Order])",
      dax: "DISTINCTCOUNT(sales_data[Sales Order])",
    },
    {
      tableau: "SUM([Sales Amount]) + SUM([Tax Amt])",
      dax: "Sales Plus Tax = SUM(sales_data[Sales Amount]) + SUM(sales_data[Tax Amt])",
    },
  ];

  return [
    {
      role: "system",
      content:
        "Translate Tableau formulas to DAX. Return strict JSON object only with key daxExpression. Use Table[Column] format, never Table.Column. Reuse existing measures and avoid duplicates.",
    },
    {
      role: "user",
      content: JSON.stringify({
        workbook: "AdventureWorks",
        formula: context.formula,
        availableTablesAndColumns: tableColumns,
        existingMeasures: context.existingMeasures,
        fewShot: fewShotExamples,
        validationFeedback: context.previousError,
      }),
    },
  ];
}

// Backward-compatible alias for previous provider naming.
export const buildGroqCalcMessages = buildCloudCalcMessages;

export function parsedWorkbookToTableColumns(parsedWorkbook: ParsedWorkbook): Record<string, string[]> {
  const byTable = new Map<string, Set<string>>();
  for (const datasource of parsedWorkbook.datasources) {
    for (const column of datasource.columns) {
      const table = column.table ?? datasource.tables[0]?.name ?? "unknown_table";
      const key = table;
      const cols = byTable.get(key) ?? new Set<string>();
      cols.add(sanitizeToken(column.name));
      byTable.set(key, cols);
    }
  }

  return Object.fromEntries(
    Array.from(byTable.entries()).map(([table, cols]) => [table, Array.from(cols.values()).sort()]),
  );
}

async function requestCloudDaxTranslation(
  context: CloudTranslationContext,
): Promise<{ daxExpression?: string; error?: string; provider?: "mistral" | "local-llama3" }> {
  const cloudApiKey = resolveCloudApiKey();
  if (cloudApiKey.length === 0) {
    return requestLocalLlamaDaxTranslation(context, "mistral_api_key_missing");
  }

  try {
    const response = await fetch(`${resolveMistralBaseUrl().replace(/\/$/, "")}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${cloudApiKey}`,
      },
      body: JSON.stringify({
        model: resolveMistralModel(),
        temperature: 0,
        messages: buildCloudCalcMessages(context),
        response_format: { type: "json_object" },
      }),
    });

    if (!response.ok) {
      return requestLocalLlamaDaxTranslation(context, `mistral_http_${response.status}`);
    }

    const data = (await response.json()) as {
      choices?: Array<{
        message?: {
          content?: string;
        };
      }>;
    };
    const content = data.choices?.[0]?.message?.content;
    if (content === undefined) {
      return requestLocalLlamaDaxTranslation(context, "mistral_empty_content");
    }
    const parsed = JSON.parse(content) as { daxExpression?: string };
    if (typeof parsed.daxExpression !== "string") {
      return requestLocalLlamaDaxTranslation(context, "mistral_missing_dax_expression");
    }
    return { daxExpression: sanitizeMistralDaxExpression(parsed.daxExpression), provider: "mistral" };
  } catch {
    return requestLocalLlamaDaxTranslation(context, "mistral_request_failed");
  }
}

async function requestLocalLlamaDaxTranslation(
  context: CloudTranslationContext,
  previousError: string,
): Promise<{ daxExpression?: string; error?: string; provider?: "local-llama3" }> {
  try {
    const endpoint = `${resolveLocalLlamaEndpoint().replace(/\/$/, "")}/api/generate`;
    const prompt =
      "Translate Tableau formula to DAX. Return strict JSON with key daxExpression only. Use Table[Column] format. " +
      JSON.stringify({
        formula: context.formula,
        previousError,
        availableTablesAndColumns: parsedWorkbookToTableColumns(context.parsedWorkbook),
        existingMeasures: context.existingMeasures,
      });

    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: resolveLocalLlamaModel(),
        prompt,
        format: "json",
        stream: false,
      }),
    });

    if (!response.ok) {
      return { error: `local_llama_http_${response.status}` };
    }

    const payload = (await response.json()) as { response?: string };
    const raw = payload.response;
    if (typeof raw !== "string" || raw.trim().length === 0) {
      return { error: "local_llama_empty_content" };
    }

    const parsed = JSON.parse(raw) as { daxExpression?: string };
    if (typeof parsed.daxExpression !== "string") {
      return { error: "local_llama_missing_dax_expression" };
    }

    return {
      daxExpression: sanitizeMistralDaxExpression(parsed.daxExpression),
      provider: "local-llama3",
    };
  } catch {
    return { error: "local_llama_request_failed" };
  }
}

async function applyCloudCalcTranslations(
  model: SemanticModel,
  parsedWorkbook: ParsedWorkbook,
): Promise<{
  semanticModel: SemanticModel;
  totalCalls: number;
  successCalls: number;
  providerStats: { mistral: number; localLlama3: number; failed: number };
}> {
  const formulasByName = new Map(parsedWorkbook.calculated_fields.map((field) => [sanitizeToken(field.name), field.formula]));
  const targetMeasureIndexes: number[] = [];

  model.measures.forEach((measure, index) => {
    if (measure.format_string === "LLM_TRANSLATION_REQUIRED") {
      targetMeasureIndexes.push(index);
    }
  });

  if (targetMeasureIndexes.length === 0) {
    return {
      semanticModel: model,
      totalCalls: 0,
      successCalls: 0,
      providerStats: { mistral: 0, localLlama3: 0, failed: 0 },
    };
  }

  const updatedMeasures = [...model.measures];
  let successCalls = 0;
  const providerStats = { mistral: 0, localLlama3: 0, failed: 0 };
  const existingMeasures = model.measures.map((measure) => `${measure.name}=${measure.expression}`);

  for (const measureIndex of targetMeasureIndexes) {
    const measure = updatedMeasures[measureIndex];
    if (measure === undefined) {
      continue;
    }
    const formula = formulasByName.get(sanitizeToken(measure.name));
    if (formula === undefined) {
      continue;
    }

    let translated: string | undefined;
    let previousError: string | undefined;
    let translationProvider: "mistral" | "local-llama3" | undefined;

    for (let attempt = 0; attempt < 2; attempt += 1) {
      const response = await requestCloudDaxTranslation({
        formula,
        parsedWorkbook,
        existingMeasures,
        ...(previousError !== undefined ? { previousError } : {}),
      });
      if (response.daxExpression === undefined) {
        previousError = response.error ?? "unknown_error";
        continue;
      }

      const validation = validateDaxExpressionForRetry(response.daxExpression);
      if (validation.valid) {
        translated = response.daxExpression;
        translationProvider = response.provider;
        break;
      }
      previousError = validation.reason ?? "validation_failed";
    }

    if (translated === undefined) {
      providerStats.failed += 1;
      continue;
    }

    if (translationProvider === "mistral") {
      providerStats.mistral += 1;
    } else {
      providerStats.localLlama3 += 1;
    }

    const base = {
      ...measure,
      expression: translated,
    };
    delete base.format_string;
    updatedMeasures[measureIndex] = base;
    successCalls += 1;
  }

  return {
    semanticModel: {
      ...model,
      measures: updatedMeasures,
    },
    totalCalls: targetMeasureIndexes.length,
    successCalls,
    providerStats,
  };
}

export function runSemanticLayerFromParsedWorkbook(
  parsedWorkbook: ParsedWorkbook,
  extraction?: TwbxExtractionResult,
): SemanticLayerOutput {
  const sourceExtraction = extractSourceTables(parsedWorkbook, extraction);
  const sourceTables = sourceExtraction.tables;
  const dashboard_spec = buildDashboardSpecFromParsedWorkbook(parsedWorkbook);
  const semantic_model = buildSemanticModelFromParsedWorkbook(parsedWorkbook);
  const data_lineage = buildLineageFromParsedWorkbook(parsedWorkbook, dashboard_spec);
  const inferredJoins = inferJoinsFromSourceTables(sourceTables);
  const inferredFactTable = inferFactTableFromSourceTables(sourceTables, inferredJoins);

  data_lineage.joins = inferredJoins;
  semantic_model.relationships = buildRelationshipsFromJoins(inferredJoins);
  semantic_model.fact_table = inferredFactTable;

  semantic_model.entities = sourceTables.map((table) => ({
    name: table.table_name,
    description: `source=${table.source}; columns=${table.columns.length}`,
  }));

  data_lineage.full_tables = sourceTables.map((table, index) => ({
    id: `full_table_${index + 1}`,
    name: table.table_name,
  }));

  data_lineage.sampled_rows = Object.fromEntries(sourceTables.map((table) => [table.table_name, table.sample_data]));
  data_lineage.full_table_profiles = sourceTables.map((table) => ({
    table_name: table.table_name,
    columns: table.columns,
    sample_data: table.sample_data,
    source: table.source,
  }));

  for (const [visualId, visualLineage] of Object.entries(data_lineage.visual_column_map)) {
    const usedTables = new Set(visualLineage.columns.map((column) => normalizeTableName(column.table)));
    const joinsUsed = inferredJoins
      .filter(
        (join) =>
          usedTables.has(normalizeTableName(join.left_table)) && usedTables.has(normalizeTableName(join.right_table)),
      )
      .map((join) => join.id);

    data_lineage.visual_column_map[visualId] = {
      ...visualLineage,
      joins_used: joinsUsed,
    };
  }

  const missingVisualColumns = findMissingVisualColumns(dashboard_spec, sourceTables);

  return {
    dashboard_spec,
    semantic_model,
    data_lineage,
    logs: [
      ...sourceExtraction.diagnostics.logs,
      `FIX_1_M_FACT_APPLIED inferred_fact_table=${inferredFactTable}`,
      "FIX_4_MEASURE_NAMES_APPLIED worksheet_kpi_mapping=CD_KPIs|PD_KPIs|SO_KPIs",
      "FIX_5_DASHBOARD_ZONE_MAPPER_APPLIED mode=zone_then_prefix_fallback",
      "FIX_6_VISUAL_TYPE_MAPPER_APPLIED fallback=tableEx",
      "FIX_2_FILTER_FK_MEASURES_ENABLED phase=transform",
      "FIX_3_LLM_CALC_PROMPT_RETRY_ENABLED phase=semantic",
      "preview generated",
    ],
    warnings: [...sourceExtraction.diagnostics.warnings, ...missingVisualColumns],
  };
}

export async function runSemanticLayerFromParsedWorkbookHybrid(
  parsedWorkbook: ParsedWorkbook,
  extraction?: TwbxExtractionResult,
): Promise<SemanticLayerOutput> {
  const deterministic = runSemanticLayerFromParsedWorkbook(parsedWorkbook, extraction);
  const calcTranslation = await applyCloudCalcTranslations(deterministic.semantic_model, parsedWorkbook);

  const context = buildSemanticEnrichmentContext(
    parsedWorkbook,
    calcTranslation.semanticModel,
    deterministic.data_lineage,
  );

  const enricher = new HybridSemanticEnricher();
  const merger = new HybridSemanticMerger();
  const llmEnrichment = await enricher.enrich(calcTranslation.semanticModel, context);

  const mergedSemantic = merger.merge({
    deterministic: calcTranslation.semanticModel,
    llm: llmEnrichment,
    glossaryOverrides: context.glossary,
  });

  const llmCalled = true;
  const llmFallback = llmEnrichment.disambiguationNotes.some((note) => note.startsWith("LLM_FALLBACK:"));
  const semanticMode = llmFallback ? "deterministic-fallback" : "mistral-or-local-llama3";

  return {
    ...deterministic,
    semantic_model: mergedSemantic,
    logs: [
      ...deterministic.logs,
      `semantic_enrichment_mode=${semanticMode}`,
      `semantic_llm_called=${llmCalled}`,
      `semantic_llm_suggestions=${llmEnrichment.suggestedMeasures.length}`,
      `calc_translation_llm_calls=${calcTranslation.totalCalls}`,
      `calc_translation_llm_success=${calcTranslation.successCalls}`,
      `calc_translation_provider_mistral=${calcTranslation.providerStats.mistral}`,
      `calc_translation_provider_local_llama3=${calcTranslation.providerStats.localLlama3}`,
      `calc_translation_provider_failed=${calcTranslation.providerStats.failed}`,
    ],
  };
}

export function buildAbstractSpecPivot(
  semanticLayer: SemanticLayerOutput,
  workbookRaw: string | Uint8Array,
  workbookName: string,
): AbstractSpec {
  const builder = new AbstractSpecBuilder();
  const base = builder.build(
    {
      raw: workbookRaw,
      source_name: workbookName,
    },
    {
      target: "powerbi",
      description: "Demo conversion from Tableau workbook",
      modifications: [
        "parse tableau workbook",
        "run semantic layer (mapping + enrichment)",
        "build abstractspec pivot",
      ],
    },
    semanticLayer.semantic_model,
    semanticLayer.data_lineage,
  );

  return {
    ...base,
    dashboard_spec: semanticLayer.dashboard_spec,
    build_log: [
      ...base.build_log,
      ...semanticLayer.logs.map((message) => ({
        level: "info" as const,
        message,
        timestamp: new Date().toISOString(),
      })),
    ],
    warnings: [
      ...base.warnings,
      ...semanticLayer.warnings.map((message) => ({
        code: message.split(":")[0] ?? "WARN",
        message,
      })),
    ],
  };
}

export function createAbstractSpecFromParsedWorkbook(
  parsedWorkbook: ParsedWorkbook,
  workbookRaw: string | Uint8Array,
  workbookName: string,
  extraction?: TwbxExtractionResult,
): AbstractSpec {
  const semanticLayer = runSemanticLayerFromParsedWorkbook(parsedWorkbook, extraction);
  return buildAbstractSpecPivot(semanticLayer, workbookRaw, workbookName);
}

export async function createAbstractSpecFromParsedWorkbookHybrid(
  parsedWorkbook: ParsedWorkbook,
  workbookRaw: string | Uint8Array,
  workbookName: string,
  extraction?: TwbxExtractionResult,
): Promise<AbstractSpec> {
  const semanticLayer = await runSemanticLayerFromParsedWorkbookHybrid(parsedWorkbook, extraction);
  return buildAbstractSpecPivot(semanticLayer, workbookRaw, workbookName);
}
