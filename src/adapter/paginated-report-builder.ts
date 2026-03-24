import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import type { AbstractSpec, ColumnRef, DashboardPage, VisualSpec } from "../spec/abstract-spec.js";
import { PowerBIQualityPipeline } from "./powerbi-quality-pipeline.js";

export interface SqlServerRdlConfig {
  server: string;
  database: string;
  integratedSecurity?: boolean;
  username?: string;
  password?: string;
  datasetName?: string;
  queryTop?: number;
  query?: string;
  fields?: Array<{ fieldName: string; sourceColumn: string }>;
}

export interface PaginatedRdlBuildOptions {
  mode?: "local" | "sqlserver";
  sqlServer?: SqlServerRdlConfig;
}

export interface PaginatedRdlConstraint {
  id: string;
  description: string;
  requiredPattern: RegExp;
}

export const PAGINATED_RDL_CONSTRAINTS: PaginatedRdlConstraint[] = [
  {
    id: "RDL-001",
    description: "Report root must exist with 2016 namespace.",
    requiredPattern: /<Report\s+xmlns="http:\/\/schemas\.microsoft\.com\/sqlserver\/reporting\/2016\/01\/reportdefinition">/,
  },
  {
    id: "RDL-002",
    description: "At least one ReportSection is required.",
    requiredPattern: /<ReportSections>\s*<ReportSection>/,
  },
  {
    id: "RDL-003",
    description: "ReportSection Width is mandatory for SSRS/Power BI Report Builder deserialization.",
    requiredPattern: /<ReportSection>[\s\S]*<\/Body>\s*<Width>[^<]+<\/Width>[\s\S]*<Page>/,
  },
  {
    id: "RDL-004",
    description: "Body Height is required.",
    requiredPattern: /<Body>[\s\S]*<Height>[^<]+<\/Height>[\s\S]*<\/Body>/,
  },
  {
    id: "RDL-005",
    description: "Page section must be present.",
    requiredPattern: /<Page>[\s\S]*<\/Page>/,
  },
  {
    id: "RDL-006",
    description: "EmbeddedData is not a valid child of Report in the 2016 report definition namespace.",
    requiredPattern: /^(?![\s\S]*<EmbeddedData>)/,
  },
  {
    id: "RDL-007",
    description: "Local paginated report must not include external ConnectString to avoid credential-mode processing errors.",
    requiredPattern: /^(?![\s\S]*<ConnectString>)/,
  },
  {
    id: "RDL-008",
    description: "Body must include visible ReportItems to avoid blank rendering.",
    requiredPattern: /<Body>[\s\S]*<ReportItems>[\s\S]*<Textbox\s+Name="[^"]+">[\s\S]*<Value>[^<]+<\/Value>[\s\S]*<\/Textbox>[\s\S]*<\/ReportItems>[\s\S]*<\/Body>/,
  },
];

export function validatePaginatedRdl(xml: string, mode: "local" | "sqlserver" = "local"): string[] {
  const issues: string[] = [];
  for (const constraint of PAGINATED_RDL_CONSTRAINTS) {
    if (mode === "sqlserver" && constraint.id === "RDL-007") {
      continue;
    }
    if (!constraint.requiredPattern.test(xml)) {
      issues.push(`${constraint.id}: ${constraint.description}`);
    }
  }
  return issues;
}

export interface RdlShapeValidationIssue {
  code: string;
  message: string;
}

export interface RdlShapeValidationReport {
  valid: boolean;
  mode: "local" | "sqlserver";
  strictMode: boolean;
  issues: RdlShapeValidationIssue[];
}

export interface RdlBusinessConstraints {
  requiredDatasetNames?: string[];
  requiredSections?: string[];
  datasetNamePattern?: RegExp | string;
  textboxNamePattern?: RegExp | string;
  tablixNamePattern?: RegExp | string;
}

export interface RdlValidationOptions {
  strictMode?: boolean;
  businessConstraints?: RdlBusinessConstraints;
}

function toRegExp(pattern: RegExp | string | undefined): RegExp | undefined {
  if (pattern === undefined) {
    return undefined;
  }
  if (pattern instanceof RegExp) {
    return pattern;
  }
  if (pattern.trim().length === 0) {
    return undefined;
  }
  return new RegExp(pattern);
}

function extractAttributeValues(xml: string, tagName: string, attributeName: string): string[] {
  const regex = new RegExp(`<${tagName}\\b[^>]*\\b${attributeName}="([^"]+)"[^>]*>`, "g");
  const values: string[] = [];
  let match = regex.exec(xml);
  while (match !== null) {
    const value = match[1];
    if (value !== undefined) {
      values.push(value);
    }
    match = regex.exec(xml);
  }
  return values;
}

function validateBusinessConstraints(
  xml: string,
  constraints?: RdlBusinessConstraints,
): RdlShapeValidationIssue[] {
  const issues: RdlShapeValidationIssue[] = [];
  if (constraints === undefined) {
    return issues;
  }

  const datasetNames = extractAttributeValues(xml, "DataSet", "Name");
  const textboxNames = extractAttributeValues(xml, "Textbox", "Name");
  const tablixNames = extractAttributeValues(xml, "Tablix", "Name");

  for (const datasetName of constraints.requiredDatasetNames ?? []) {
    if (!datasetNames.includes(datasetName)) {
      issues.push({
        code: "RDL-BIZ-001",
        message: `Required dataset is missing: ${datasetName}`,
      });
    }
  }

  for (const sectionName of constraints.requiredSections ?? []) {
    const sectionPattern = new RegExp(`<${sectionName}\\b|<${sectionName}>`);
    if (!sectionPattern.test(xml)) {
      issues.push({
        code: "RDL-BIZ-002",
        message: `Required section is missing: ${sectionName}`,
      });
    }
  }

  const datasetNamePattern = toRegExp(constraints.datasetNamePattern);
  if (datasetNamePattern !== undefined) {
    for (const name of datasetNames) {
      if (!datasetNamePattern.test(name)) {
        issues.push({
          code: "RDL-BIZ-003",
          message: `Dataset naming convention violation: ${name}`,
        });
      }
    }
  }

  const textboxNamePattern = toRegExp(constraints.textboxNamePattern);
  if (textboxNamePattern !== undefined) {
    for (const name of textboxNames) {
      if (!textboxNamePattern.test(name)) {
        issues.push({
          code: "RDL-BIZ-004",
          message: `Textbox naming convention violation: ${name}`,
        });
      }
    }
  }

  const tablixNamePattern = toRegExp(constraints.tablixNamePattern);
  if (tablixNamePattern !== undefined) {
    for (const name of tablixNames) {
      if (!tablixNamePattern.test(name)) {
        issues.push({
          code: "RDL-BIZ-005",
          message: `Tablix naming convention violation: ${name}`,
        });
      }
    }
  }

  return issues;
}

export function validateGeneratedRdlShape(
  xml: string,
  mode: "local" | "sqlserver" = "local",
  options: RdlValidationOptions = {},
): RdlShapeValidationReport {
  const issues: RdlShapeValidationIssue[] = [];
  const strictMode = options.strictMode ?? false;

  const trimmed = xml.trim();
  if (!/^(?:<\?xml[\s\S]*?\?>\s*)?<Report\s+/m.test(trimmed)) {
    issues.push({
      code: "RDL-SHAPE-001",
      message: "RDL must start with <Report ...> root element.",
    });
  }

  if (/```/m.test(trimmed)) {
    issues.push({
      code: "RDL-SHAPE-002",
      message: "RDL must be raw XML and must not include markdown fences.",
    });
  }

  if (!/<ReportSections>[\s\S]*<ReportSection>[\s\S]*<Body>[\s\S]*<ReportItems>/m.test(trimmed)) {
    issues.push({
      code: "RDL-SHAPE-003",
      message: "RDL must include ReportSections/ReportSection/Body/ReportItems hierarchy.",
    });
  }

  if (mode === "local" && /<ConnectString>/m.test(trimmed)) {
    issues.push({
      code: "RDL-SHAPE-004",
      message: "Local mode RDL must not include ConnectString.",
    });
  }

  const constraintIssues = validatePaginatedRdl(trimmed, mode);
  for (const issue of constraintIssues) {
    issues.push({
      code: "RDL-CONSTRAINT",
      message: issue,
    });
  }

  if (strictMode) {
    issues.push(...validateBusinessConstraints(trimmed, options.businessConstraints));
  }

  return {
    valid: issues.length === 0,
    mode,
    strictMode,
    issues,
  };
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function formatColumnRef(column?: ColumnRef): string {
  if (column === undefined) {
    return "-";
  }
  return `${column.table}.${column.column}`;
}

function toSqlIdentifier(name: string): string {
  return `[${name.replace(/\]/g, "]]" )}]`;
}

function sanitizeFieldName(name: string, index: number): string {
  const cleaned = name.replace(/[^a-zA-Z0-9_]/g, "_").replace(/^_+/, "");
  const fallback = `field_${index + 1}`;
  return cleaned.length > 0 ? cleaned : fallback;
}

function deriveSqlDataset(spec: AbstractSpec): {
  tableName: string;
  fields: Array<{ fieldName: string; sourceColumn: string }>;
} {
  const factTable = spec.semantic_model.fact_table;
  const profiles = spec.data_lineage.full_table_profiles ?? [];
  const factProfile = profiles.find((profile) => profile.table_name.toLowerCase() === factTable.toLowerCase());
  const selectedProfile = factProfile ?? profiles[0];

  const columnsFromProfile = selectedProfile?.columns.map((column, index) => ({
    fieldName: sanitizeFieldName(column.name, index),
    sourceColumn: column.name,
  }));

  const fallbackColumns = Array.from(
    new Map(
      spec.data_lineage.columns_used.map((usage) => [
        `${usage.column.table}.${usage.column.column}`.toLowerCase(),
        usage.column.column,
      ]),
    ).values(),
  ).map((column, index) => ({
    fieldName: sanitizeFieldName(column, index),
    sourceColumn: column,
  }));

  const fields = (columnsFromProfile ?? fallbackColumns)
    .slice(0, 8)
    .filter((field, index, list) => list.findIndex((item) => item.fieldName === field.fieldName) === index);

  const tableName = selectedProfile?.table_name ?? spec.data_lineage.full_tables?.[0]?.name ?? spec.data_lineage.tables[0]?.name ?? factTable;

  if (fields.length === 0) {
    return {
      tableName,
      fields: [{ fieldName: "table_name", sourceColumn: "table_name" }],
    };
  }

  return { tableName, fields };
}

function buildSqlConnectString(config: SqlServerRdlConfig): string {
  const parts = [`Data Source=${config.server}`, `Initial Catalog=${config.database}`];
  if (config.integratedSecurity !== false) {
    parts.push("Integrated Security=True");
  } else if ((config.username?.length ?? 0) > 0) {
    parts.push(`User ID=${config.username}`);
    if ((config.password?.length ?? 0) > 0) {
      parts.push(`Password=${config.password}`);
    }
  }
  return parts.join(";");
}

function buildSqlDataSourcesXml(config: SqlServerRdlConfig): string {
  return `
  <DataSources>
    <DataSource Name="AdventureWorksDW2022_Source">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>${escapeXml(buildSqlConnectString(config))}</ConnectString>
        <IntegratedSecurity>${config.integratedSecurity === false ? "false" : "true"}</IntegratedSecurity>
      </ConnectionProperties>
    </DataSource>
  </DataSources>`;
}

function buildSqlDataSetsXml(spec: AbstractSpec, config: SqlServerRdlConfig): {
  xml: string;
  datasetName: string;
  fields: Array<{ fieldName: string; sourceColumn: string }>;
} {
  const dataset = deriveSqlDataset(spec);
  const datasetName = config.datasetName ?? "MainDataset";
  const topN = config.queryTop ?? 200;
  const selectedFields =
    (config.fields ?? dataset.fields)
      .filter((field) => field.fieldName.trim().length > 0 && field.sourceColumn.trim().length > 0)
      .map((field, index) => ({
        fieldName: sanitizeFieldName(field.fieldName, index),
        sourceColumn: field.sourceColumn,
      }))
      .slice(0, 12) || [];

  const effectiveFields = selectedFields.length > 0 ? selectedFields : dataset.fields;
  const selectList = effectiveFields.map((field) => toSqlIdentifier(field.sourceColumn)).join(", ");
  const defaultCommandText = `SELECT TOP ${topN} ${selectList} FROM ${toSqlIdentifier(dataset.tableName)}`;
  const commandText = config.query?.trim().length ? config.query.trim() : defaultCommandText;

  const fieldsXml = effectiveFields
    .map(
      (field) => `
        <Field Name="${escapeXml(field.fieldName)}">
          <DataField>${escapeXml(field.sourceColumn)}</DataField>
        </Field>`,
    )
    .join("");

  return {
    datasetName,
    fields: effectiveFields,
    xml: `
  <DataSets>
    <DataSet Name="${escapeXml(datasetName)}">
      <Query>
        <DataSourceName>AdventureWorksDW2022_Source</DataSourceName>
        <CommandText>${escapeXml(commandText)}</CommandText>
      </Query>
      <Fields>${fieldsXml}
      </Fields>
    </DataSet>
  </DataSets>`,
  };
}

function buildSqlTablix(datasetName: string, fields: Array<{ fieldName: string; sourceColumn: string }>): string {
  const columns = fields
    .map(
      () => `
              <TablixColumn>
                <Width>1.2in</Width>
              </TablixColumn>`,
    )
    .join("");

  const headerCells = fields
    .map(
      (field, index) => `
                  <TablixCell>
                    <CellContents>
                      <Textbox Name="tbHeader_${index + 1}">
                        <CanGrow>true</CanGrow>
                        <KeepTogether>true</KeepTogether>
                        <Paragraphs>
                          <Paragraph>
                            <TextRuns>
                              <TextRun>
                                <Value>${escapeXml(field.sourceColumn)}</Value>
                                <Style><FontWeight>Bold</FontWeight></Style>
                              </TextRun>
                            </TextRuns>
                            <Style />
                          </Paragraph>
                        </Paragraphs>
                        <Style>
                          <Border><Style>Solid</Style></Border>
                          <PaddingLeft>2pt</PaddingLeft>
                          <PaddingRight>2pt</PaddingRight>
                          <PaddingTop>2pt</PaddingTop>
                          <PaddingBottom>2pt</PaddingBottom>
                        </Style>
                      </Textbox>
                    </CellContents>
                  </TablixCell>`,
    )
    .join("");

  const detailCells = fields
    .map(
      (field, index) => `
                  <TablixCell>
                    <CellContents>
                      <Textbox Name="tbDetail_${index + 1}">
                        <CanGrow>true</CanGrow>
                        <KeepTogether>true</KeepTogether>
                        <Paragraphs>
                          <Paragraph>
                            <TextRuns>
                              <TextRun>
                                <Value>=Fields!${escapeXml(field.fieldName)}.Value</Value>
                                <Style />
                              </TextRun>
                            </TextRuns>
                            <Style />
                          </Paragraph>
                        </Paragraphs>
                        <Style>
                          <Border><Style>Solid</Style></Border>
                          <PaddingLeft>2pt</PaddingLeft>
                          <PaddingRight>2pt</PaddingRight>
                          <PaddingTop>2pt</PaddingTop>
                          <PaddingBottom>2pt</PaddingBottom>
                        </Style>
                      </Textbox>
                    </CellContents>
                  </TablixCell>`,
    )
    .join("");

  const columnMembers = fields.map(() => "<TablixMember />").join("");

  return `
          <Tablix Name="tablixAdventureWorks">
            <TablixBody>
              <TablixColumns>${columns}
              </TablixColumns>
              <TablixRows>
                <TablixRow>
                  <Height>0.25in</Height>
                  <TablixCells>${headerCells}
                  </TablixCells>
                </TablixRow>
                <TablixRow>
                  <Height>0.25in</Height>
                  <TablixCells>${detailCells}
                  </TablixCells>
                </TablixRow>
              </TablixRows>
            </TablixBody>
            <TablixColumnHierarchy>
              <TablixMembers>${columnMembers}</TablixMembers>
            </TablixColumnHierarchy>
            <TablixRowHierarchy>
              <TablixMembers>
                <TablixMember>
                  <KeepWithGroup>After</KeepWithGroup>
                  <RepeatOnNewPage>true</RepeatOnNewPage>
                </TablixMember>
                <TablixMember>
                  <Group Name="DetailGroup" />
                </TablixMember>
              </TablixMembers>
            </TablixRowHierarchy>
            <DataSetName>${escapeXml(datasetName)}</DataSetName>
            <Top>6.1in</Top>
            <Left>0.2in</Left>
            <Height>3.7in</Height>
            <Width>9.5in</Width>
            <Style>
              <Border><Style>Solid</Style></Border>
            </Style>
          </Tablix>`;
}

function renderVisualLines(page: DashboardPage): string {
  if (page.visuals.length === 0) {
    return "Aucun visuel detecte";
  }

  return page.visuals
    .map((visual: VisualSpec, index) => {
      const axes = visual.data_binding.axes;
      const bindings = [
        `x=${formatColumnRef(axes.x)}`,
        `y=${formatColumnRef(axes.y)}`,
        `color=${formatColumnRef(axes.color)}`,
        `size=${formatColumnRef(axes.size)}`,
        `tooltip=${formatColumnRef(axes.tooltip)}`,
      ].join(" | ");

      const title = visual.title ?? visual.id;
      return `${index + 1}. ${title} [${visual.type}] => ${bindings}`;
    })
    .join("\n");
}

function buildBodyReportItems(
  spec: AbstractSpec,
  options?: {
    sqlTablix?: string;
  },
): string {
  const pageCount = spec.dashboard_spec.pages.length;
  const visualCount = spec.dashboard_spec.pages.reduce((acc, page) => acc + page.visuals.length, 0);
  const measureCount = spec.export_manifest.dax_measures.length;
  const pageNames = spec.dashboard_spec.pages.map((page) => page.name).join(", ");
  const firstPage = spec.dashboard_spec.pages[0];
  const firstPageSummary = firstPage === undefined ? "No page available" : renderVisualLines(firstPage);

  const summaryText = [
    `Dataset: ${spec.export_manifest.model_config.dataset_name}`,
    `Fact table: ${spec.semantic_model.fact_table}`,
    `Pages: ${pageCount}`,
    `Visuals: ${visualCount}`,
    `Measures: ${measureCount}`,
    `Page names: ${pageNames}`,
  ].join("\n");

  const firstPageText = `First page details\n${firstPageSummary}`;

  const measurePreview = spec.export_manifest.dax_measures
    .slice(0, 12)
    .map((measure, index) => `${index + 1}. ${measure.name} = ${measure.expression}`)
    .join("\n");

  return `
        <ReportItems>
          <Textbox Name="tbTitle">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>${escapeXml(spec.export_manifest.model_config.dataset_name)} - Paginated Report</Value>
                    <Style>
                      <FontSize>16pt</FontSize>
                      <FontWeight>Bold</FontWeight>
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style />
              </Paragraph>
            </Paragraphs>
            <Top>0.1in</Top>
            <Left>0.2in</Left>
            <Height>0.5in</Height>
            <Width>9.5in</Width>
            <Style>
              <Border><Style>None</Style></Border>
              <PaddingLeft>2pt</PaddingLeft>
              <PaddingRight>2pt</PaddingRight>
              <PaddingTop>2pt</PaddingTop>
              <PaddingBottom>2pt</PaddingBottom>
            </Style>
          </Textbox>
          <Textbox Name="tbSummary">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>${escapeXml(summaryText)}</Value>
                    <Style>
                      <FontSize>10pt</FontSize>
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style />
              </Paragraph>
            </Paragraphs>
            <Top>0.7in</Top>
            <Left>0.2in</Left>
            <Height>1.7in</Height>
            <Width>9.5in</Width>
            <Style>
              <Border><Style>Solid</Style></Border>
              <PaddingLeft>4pt</PaddingLeft>
              <PaddingRight>4pt</PaddingRight>
              <PaddingTop>4pt</PaddingTop>
              <PaddingBottom>4pt</PaddingBottom>
            </Style>
          </Textbox>
          <Textbox Name="tbFirstPage">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>${escapeXml(firstPageText)}</Value>
                    <Style>
                      <FontSize>9pt</FontSize>
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style />
              </Paragraph>
            </Paragraphs>
            <Top>2.55in</Top>
            <Left>0.2in</Left>
            <Height>3.4in</Height>
            <Width>9.5in</Width>
            <Style>
              <Border><Style>Solid</Style></Border>
              <PaddingLeft>4pt</PaddingLeft>
              <PaddingRight>4pt</PaddingRight>
              <PaddingTop>4pt</PaddingTop>
              <PaddingBottom>4pt</PaddingBottom>
            </Style>
          </Textbox>
          <Textbox Name="tbMeasures">
            <CanGrow>true</CanGrow>
            <KeepTogether>true</KeepTogether>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>${escapeXml(`Measure preview\n${measurePreview}`)}</Value>
                    <Style>
                      <FontSize>9pt</FontSize>
                    </Style>
                  </TextRun>
                </TextRuns>
                <Style />
              </Paragraph>
            </Paragraphs>
            <Top>6.1in</Top>
            <Left>0.2in</Left>
            <Height>3.7in</Height>
            <Width>9.5in</Width>
            <Style>
              <Border><Style>Solid</Style></Border>
              <PaddingLeft>4pt</PaddingLeft>
              <PaddingRight>4pt</PaddingRight>
              <PaddingTop>4pt</PaddingTop>
              <PaddingBottom>4pt</PaddingBottom>
            </Style>
          </Textbox>
          ${options?.sqlTablix ?? ""}
        </ReportItems>`;
}

export function buildPaginatedRdl(spec: AbstractSpec, options?: PaginatedRdlBuildOptions): string {
  const mode = options?.mode ?? "local";
  const sqlConfig = options?.sqlServer;
  const reportName = `${spec.export_manifest.model_config.dataset_name}-paginated`;
  const pageSummary = spec.dashboard_spec.pages
    .map((page) => `${page.name}: ${renderVisualLines(page)}`)
    .join("\n");
  const measureSummary = spec.export_manifest.dax_measures.map((measure) => `${measure.name}=${measure.expression}`).join(" | ");
  const themeSummary = spec.dashboard_spec.theme.palette.join(", ");
  const datasetSummary = (spec.data_lineage.full_tables ?? spec.data_lineage.tables)
    .map((table) => `Dataset_${table.name.replace(/[^a-zA-Z0-9_]/g, "_")}`)
    .join(", ");

  const sqlDataSets = mode === "sqlserver" && sqlConfig !== undefined ? buildSqlDataSetsXml(spec, sqlConfig) : undefined;
  const sqlDataSourcesXml = mode === "sqlserver" && sqlConfig !== undefined ? buildSqlDataSourcesXml(sqlConfig) : "";
  const sqlDataSetsXml = sqlDataSets?.xml ?? "";
  const sqlTablix =
    mode === "sqlserver" && sqlDataSets !== undefined
      ? buildSqlTablix(sqlDataSets.datasetName, sqlDataSets.fields)
      : "";

  return `<?xml version="1.0" encoding="utf-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition">
  <AutoRefresh>0</AutoRefresh>
  <Description>${escapeXml(
    mode === "sqlserver"
      ? `${reportName} generated in SQL Server mode with external datasource.`
      : `${reportName} generated in local mode without external datasource.`,
  )}</Description>
  <CustomProperties>
    <CustomProperty>
      <Name>ReportName</Name>
      <Value>${escapeXml(reportName)}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>AbstractSpecId</Name>
      <Value>${escapeXml(spec.id)}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>ThemeName</Name>
      <Value>${escapeXml(spec.dashboard_spec.theme.name)}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>PageSummary</Name>
      <Value>${escapeXml(pageSummary)}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>MeasureSummary</Name>
      <Value>${escapeXml(measureSummary)}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>ThemePalette</Name>
      <Value>${escapeXml(themeSummary)}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>ExecutionMode</Name>
      <Value>${mode === "sqlserver" ? "SqlServerDataSource" : "LocalNoDataSource"}</Value>
    </CustomProperty>
    <CustomProperty>
      <Name>DatasetsPerTable</Name>
      <Value>${escapeXml(datasetSummary)}</Value>
    </CustomProperty>
  </CustomProperties>
${sqlDataSourcesXml}
${sqlDataSetsXml}
  <ReportSections>
    <ReportSection>
      <Body>
${buildBodyReportItems(spec, { sqlTablix })}
        <Height>11in</Height>
      </Body>
      <Width>10in</Width>
      <Page>
        <PageHeader>
          <Height>0.6in</Height>
          <PrintOnFirstPage>true</PrintOnFirstPage>
          <PrintOnLastPage>true</PrintOnLastPage>
        </PageHeader>
        <PageFooter>
          <Height>0.4in</Height>
          <PrintOnFirstPage>true</PrintOnFirstPage>
          <PrintOnLastPage>true</PrintOnLastPage>
        </PageFooter>
      </Page>
    </ReportSection>
  </ReportSections>
</Report>`;
}

export async function writePaginatedRdl(
  spec: AbstractSpec,
  outputDir: string,
  validationOptions: RdlValidationOptions = {},
): Promise<string> {
  const qualityPipeline = new PowerBIQualityPipeline();
  const quality = qualityPipeline.prepareSpec(spec);
  if (!quality.valid) {
    const details = quality.issues.map((issue) => `${issue.stage}:${issue.code}`).join(", ");
    throw new Error(`Paginated report quality checks failed: ${details}`);
  }

  const filePath = path.join(outputDir, "powerbi-paginated-report.rdl");
  const content = buildPaginatedRdl(quality.fixedSpec);
  const validation = validateGeneratedRdlShape(content, "local", validationOptions);
  if (!validation.valid) {
    throw new Error(`Paginated RDL shape validation failed: ${validation.issues.map((issue) => `${issue.code}:${issue.message}`).join(" | ")}`);
  }

  await mkdir(outputDir, { recursive: true });
  await writeFile(filePath, content, "utf8");
  await writeFile(
    `${filePath}.validation.json`,
    JSON.stringify(validation, null, 2),
    "utf8",
  );
  return filePath;
}

export async function writePaginatedRdlSqlServer(
  spec: AbstractSpec,
  outputDir: string,
  config: SqlServerRdlConfig,
  validationOptions: RdlValidationOptions = {},
): Promise<string> {
  const qualityPipeline = new PowerBIQualityPipeline();
  const quality = qualityPipeline.prepareSpec(spec);
  if (!quality.valid) {
    const details = quality.issues.map((issue) => `${issue.stage}:${issue.code}`).join(", ");
    throw new Error(`Paginated report quality checks failed: ${details}`);
  }

  const filePath = path.join(outputDir, "powerbi-paginated-report-sqlserver.rdl");
  const content = buildPaginatedRdl(quality.fixedSpec, {
    mode: "sqlserver",
    sqlServer: config,
  });
  const validation = validateGeneratedRdlShape(content, "sqlserver", validationOptions);
  if (!validation.valid) {
    throw new Error(`Paginated RDL shape validation failed: ${validation.issues.map((issue) => `${issue.code}:${issue.message}`).join(" | ")}`);
  }

  await mkdir(outputDir, { recursive: true });
  await writeFile(filePath, content, "utf8");
  await writeFile(
    `${filePath}.validation.json`,
    JSON.stringify(validation, null, 2),
    "utf8",
  );
  return filePath;
}
