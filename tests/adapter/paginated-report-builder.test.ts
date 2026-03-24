import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  buildPaginatedRdl,
  PAGINATED_RDL_CONSTRAINTS,
  validateGeneratedRdlShape,
  validatePaginatedRdl,
  writePaginatedRdl,
  writePaginatedRdlSqlServer,
} from "../../src/adapter/paginated-report-builder.js";
import type { AbstractSpec } from "../../src/spec/abstract-spec.js";

const spec: AbstractSpec = {
  id: "spec-paginated",
  version: "0.1.0",
  source_fingerprint: "abc123",
  dashboard_spec: {
    pages: [
      {
        id: "page-1",
        name: "Executive",
        visuals: [
          {
            id: "v1",
            source_worksheet: "Sheet1",
            type: "bar",
            position: { row: 0, column: 0, row_span: 1, column_span: 1 },
            data_binding: {
              axes: {
                x: { table: "sales_data", column: "Region" },
                y: { table: "sales_data", column: "Sales" },
              },
            },
            title: "Sales by Region",
          },
        ],
      },
    ],
    global_filters: [],
    theme: { name: "demo", palette: ["#123456", "#654321"] },
    refresh_policy: { mode: "manual" },
  },
  semantic_model: {
    entities: [],
    measures: [{ name: "Total Sales", expression: "SUM(sales_data[Sales])" }],
    dimensions: [],
    hierarchies: [],
    relationships: [],
    glossary: [],
    fact_table: "sales_data",
    grain: "row",
  },
  data_lineage: {
    tables: [{ id: "t1", name: "sales_data" }],
    joins: [],
    columns_used: [],
    visual_column_map: {},
  },
  export_manifest: {
    target: "powerbi",
    model_config: { dataset_name: "dataset_demo" },
    dax_measures: [{ name: "Total Sales", expression: "SUM(sales_data[Sales])" }],
    m_queries: [{ name: "sales_data", query: "let Source = sales_data in Source" }],
    post_export_hooks: [],
  },
  build_log: [],
  warnings: [],
};

test("buildPaginatedRdl genere un document rdl avec les sections attendues", () => {
  const xml = buildPaginatedRdl(spec);
  assert.ok(xml.includes("<Report "));
  assert.ok(xml.includes("dataset_demo-paginated"));
  assert.ok(xml.includes("Sales by Region"));
  assert.ok(xml.includes("<CustomProperties>"));
  assert.ok(xml.includes("Dataset_sales_data"));
  assert.ok(xml.includes("<ReportItems>"));
  assert.ok(xml.includes("<Textbox Name=\"tbTitle\">"));
  assert.ok(xml.includes("Paginated Report"));
  assert.equal(xml.includes("<EmbeddedData>"), false);
  assert.equal(xml.includes("<DataSources>"), false);
  assert.equal(xml.includes("<ConnectString>"), false);
  assert.ok(xml.includes("<Width>10in</Width>"));
});

test("validatePaginatedRdl applique les contraintes obligatoires", () => {
  const xml = buildPaginatedRdl(spec);
  const issues = validatePaginatedRdl(xml);
  assert.equal(issues.length, 0);
  assert.equal(PAGINATED_RDL_CONSTRAINTS.length >= 5, true);

  const shape = validateGeneratedRdlShape(xml, "local");
  assert.equal(shape.valid, true);
  assert.equal(shape.issues.length, 0);
});

test("validateGeneratedRdlShape detecte un wrapper markdown", () => {
  const xml = "```xml\n" + buildPaginatedRdl(spec) + "\n```";
  const report = validateGeneratedRdlShape(xml, "local");
  assert.equal(report.valid, false);
  assert.equal(report.issues.some((issue) => issue.code === "RDL-SHAPE-002"), true);
});

test("validateGeneratedRdlShape strict applique les contraintes metier personnalisées", () => {
  const xml = buildPaginatedRdl(spec, {
    mode: "sqlserver",
    sqlServer: {
      server: "localhost\\sqlexpress",
      database: "AdventureWorksDW2022",
      integratedSecurity: true,
      datasetName: "MainDataset",
    },
  });

  const strictPass = validateGeneratedRdlShape(xml, "sqlserver", {
    strictMode: true,
    businessConstraints: {
      requiredDatasetNames: ["MainDataset"],
      requiredSections: ["PageHeader", "PageFooter", "ReportItems"],
      datasetNamePattern: "^MainDataset$",
      textboxNamePattern: "^tb[A-Z][A-Za-z0-9_]*$",
      tablixNamePattern: "^tablix[A-Za-z0-9_]+$",
    },
  });

  assert.equal(strictPass.valid, true);
  assert.equal(strictPass.strictMode, true);

  const strictFail = validateGeneratedRdlShape(xml, "sqlserver", {
    strictMode: true,
    businessConstraints: {
      requiredDatasetNames: ["DatasetObligatoireInexistant"],
    },
  });

  assert.equal(strictFail.valid, false);
  assert.equal(strictFail.issues.some((issue) => issue.code === "RDL-BIZ-001"), true);
});

test("validatePaginatedRdl detecte la suppression de Width", () => {
  const xml = buildPaginatedRdl(spec).replace("<Width>10in</Width>", "");
  const issues = validatePaginatedRdl(xml);
  assert.equal(issues.some((issue) => issue.includes("RDL-003")), true);
});

test("validatePaginatedRdl detecte EmbeddedData interdit", () => {
  const xml = buildPaginatedRdl(spec).replace("</Report>", "<EmbeddedData><X>1</X></EmbeddedData></Report>");
  const issues = validatePaginatedRdl(xml);
  assert.equal(issues.some((issue) => issue.includes("RDL-006")), true);
});

test("validatePaginatedRdl detecte ConnectString interdit", () => {
  const xml = buildPaginatedRdl(spec).replace("</Report>", "<DataSources><DataSource Name=\"x\"><ConnectionProperties><ConnectString>Data Source=(local)</ConnectString></ConnectionProperties></DataSource></DataSources></Report>");
  const issues = validatePaginatedRdl(xml);
  assert.equal(issues.some((issue) => issue.includes("RDL-007")), true);
});

test("writePaginatedRdl ecrit output/powerbi-paginated-report.rdl", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "coeur-rdl-"));
  const outputPath = await writePaginatedRdl(spec, root);
  const content = await readFile(outputPath, "utf8");
  const validationRaw = await readFile(`${outputPath}.validation.json`, "utf8");
  const validation = JSON.parse(validationRaw) as { valid?: boolean };

  assert.ok(outputPath.endsWith("powerbi-paginated-report.rdl"));
  assert.ok(content.includes("AbstractSpecId"));
  assert.equal(validation.valid, true);

  await rm(root, { recursive: true, force: true });
});

test("buildPaginatedRdl mode sqlserver inclut datasource, datasets et connect string", () => {
  const xml = buildPaginatedRdl(spec, {
    mode: "sqlserver",
    sqlServer: {
      server: "localhost\\sqlexpress",
      database: "AdventureWorksDW2022",
      integratedSecurity: true,
    },
  });

  assert.equal(xml.includes("<DataSources>"), true);
  assert.equal(xml.includes("<DataSets>"), true);
  assert.equal(xml.includes("AdventureWorksDW2022_Source"), true);
  assert.equal(xml.includes("<ConnectString>"), true);
  assert.equal(validatePaginatedRdl(xml, "sqlserver").length, 0);
});

test("writePaginatedRdlSqlServer ecrit output/powerbi-paginated-report-sqlserver.rdl", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "coeur-rdl-sql-"));
  const outputPath = await writePaginatedRdlSqlServer(spec, root, {
    server: "localhost\\sqlexpress",
    database: "AdventureWorksDW2022",
    integratedSecurity: true,
  });
  const content = await readFile(outputPath, "utf8");
  const validationRaw = await readFile(`${outputPath}.validation.json`, "utf8");
  const validation = JSON.parse(validationRaw) as { valid?: boolean };

  assert.ok(outputPath.endsWith("powerbi-paginated-report-sqlserver.rdl"));
  assert.equal(content.includes("<ConnectString>"), true);
  assert.equal(content.includes("<DataSet Name=\"MainDataset\">"), true);
  assert.equal(validation.valid, true);

  await rm(root, { recursive: true, force: true });
});

test("writePaginatedRdlSqlServer strict echoue si contrainte metier invalide", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "coeur-rdl-sql-strict-"));

  await assert.rejects(
    () =>
      writePaginatedRdlSqlServer(
        spec,
        root,
        {
          server: "localhost\\sqlexpress",
          database: "AdventureWorksDW2022",
          integratedSecurity: true,
          datasetName: "MainDataset",
        },
        {
          strictMode: true,
          businessConstraints: {
            requiredDatasetNames: ["DatasetObligatoireInexistant"],
          },
        },
      ),
    /RDL-BIZ-001/,
  );

  await rm(root, { recursive: true, force: true });
});
