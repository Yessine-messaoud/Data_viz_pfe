import test from "node:test";
import assert from "node:assert/strict";

import { createAbstractSpecFromParsedWorkbook } from "../../src/demo/parsed-workbook-to-abstract.js";
import type { ParsedWorkbook, TwbxExtractionResult } from "../../src/tableau/interfaces.js";

const parsedWorkbook: ParsedWorkbook = {
  worksheets: [
    {
      id: "ws1",
      name: "Sales",
      rows: ["[Sales]"],
      cols: ["[Region]"],
      marks: ["bar"],
      filters: ["[Category]"],
    },
  ],
  datasources: [
    {
      id: "ds1",
      name: "MainDS",
      tables: [{ name: "fact_sales" }],
      columns: [
        { id: "[Sales]", name: "[Sales]", dataType: "real", table: "fact_sales" },
        { id: "[Region]", name: "[Region]", dataType: "string", table: "fact_sales" },
        { id: "[Category]", name: "[Category]", dataType: "string", table: "fact_sales" },
      ],
    },
  ],
  calculated_fields: [{ id: "cf1", name: "Profit Ratio", formula: "SUM([Profit])/SUM([Sales])" }],
  dashboards: [{ id: "db1", name: "Main Dashboard", zones: [] }],
  parameters: [],
};

test("genere une abstract visualization JSON depuis ParsedWorkbook", () => {
  const spec = createAbstractSpecFromParsedWorkbook(parsedWorkbook, "<workbook />", "demo.twb");

  assert.equal(spec.export_manifest.target, "powerbi");
  assert.equal(spec.dashboard_spec.pages.length, 1);
  assert.equal(spec.dashboard_spec.pages[0]?.visuals.length, 1);
  assert.equal(spec.semantic_model.fact_table, "fact_sales");
  assert.equal(spec.data_lineage.visual_column_map["visual_1"]?.columns.length, 3);
  assert.equal((spec.data_lineage.full_tables?.length ?? 0) >= 1, true);
  assert.equal(spec.semantic_model.measures.some((measure) => measure.name === "Profit Ratio"), true);
});

test("fallback des axes x/y si worksheet rows/cols vides", () => {
  const sparseWorkbook: ParsedWorkbook = {
    ...parsedWorkbook,
    worksheets: [
      {
        id: "ws_sparse",
        name: "Sparse",
        rows: [],
        cols: [],
        marks: ["bar"],
        filters: [],
      },
    ],
  };

  const spec = createAbstractSpecFromParsedWorkbook(sparseWorkbook, "<workbook />", "sparse.twb");
  const visual = spec.dashboard_spec.pages[0]?.visuals[0];
  assert.notEqual(visual, undefined);
  assert.notEqual(visual?.data_binding.axes.x, undefined);
  assert.notEqual(visual?.data_binding.axes.y, undefined);
});

test("inference de joins et relationships entre tables source", () => {
  const joinWorkbook: ParsedWorkbook = {
    ...parsedWorkbook,
    datasources: [
      {
        id: "sales_ds",
        name: "SalesDS",
        tables: [{ name: "sales_data" }],
        columns: [
          { id: "[CustomerId]", name: "[CustomerId]", dataType: "integer", table: "sales_data" },
          { id: "[Sales]", name: "[Sales]", dataType: "real", table: "sales_data" },
        ],
      },
      {
        id: "customer_ds",
        name: "CustomerDS",
        tables: [{ name: "customer_data" }],
        columns: [
          { id: "[CustomerId]", name: "[CustomerId]", dataType: "integer", table: "customer_data" },
          { id: "[CustomerName]", name: "[CustomerName]", dataType: "string", table: "customer_data" },
        ],
      },
    ],
  };

  const spec = createAbstractSpecFromParsedWorkbook(joinWorkbook, "<workbook />", "join.twb");
  assert.equal(spec.data_lineage.joins.length > 0, true);
  assert.equal(spec.semantic_model.relationships.length > 0, true);
});

test("construit les full tables depuis datasource twb meme sans hyper", () => {
  const spec = createAbstractSpecFromParsedWorkbook(parsedWorkbook, "<workbook />", "demo.twb");
  const fullTableNames = (spec.data_lineage.full_tables ?? []).map((table) => table.name);
  assert.equal(fullTableNames.includes("fact_sales"), true);
  assert.equal(spec.data_lineage.sampled_rows?.fact_sales !== undefined, true);
});

test("enrichit full tables et sample data depuis twbx hyper", () => {
  const extraction: TwbxExtractionResult = {
    twbContent: "<workbook />",
    twbPath: "workbook.twb",
    dataFiles: [
      {
        path: "Data/fact_sales.hyper",
        type: "hyper",
        bytes: new Uint8Array([1, 2, 3, 4, 5, 6]),
      },
    ],
  };

  const spec = createAbstractSpecFromParsedWorkbook(parsedWorkbook, new Uint8Array([1, 2, 3]), "demo.twbx", extraction);
  const names = (spec.data_lineage.full_tables ?? []).map((table) => table.name.toLowerCase());
  assert.equal(names.includes("fact_sales"), true);
  assert.equal((spec.data_lineage.sampled_rows?.fact_sales?.length ?? 0) > 0, true);
});

test("warn si visuel utilise une colonne absente des tables extraites", () => {
  const inconsistentWorkbook: ParsedWorkbook = {
    ...parsedWorkbook,
    worksheets: [
      {
        id: "ws_missing",
        name: "Missing",
        rows: ["[UnknownMeasure]"],
        cols: ["[UnknownDimension]"],
        marks: ["bar"],
        filters: [],
      },
    ],
  };

  const spec = createAbstractSpecFromParsedWorkbook(inconsistentWorkbook, "<workbook />", "inconsistent.twb");
  assert.equal(
    spec.warnings.some((warning) => warning.code === "WARN_VISUAL_COLUMN_NOT_FOUND"),
    true,
  );
});

test("fail si aucune table n'est detectee depuis datasource", () => {
  const emptyWorkbook: ParsedWorkbook = {
    worksheets: parsedWorkbook.worksheets,
    datasources: [],
    calculated_fields: [],
    dashboards: [],
    parameters: [],
  };

  assert.throws(() => createAbstractSpecFromParsedWorkbook(emptyWorkbook, "<workbook />", "empty.twb"));
});

test("FIX1 detecte sales_data comme fact_table via score FK/join/mesures", () => {
  const workbook: ParsedWorkbook = {
    ...parsedWorkbook,
    datasources: [
      {
        id: "d_customer",
        name: "CustomerDS",
        tables: [{ name: "customer_data" }],
        columns: [
          { id: "[CustomerKey]", name: "[CustomerKey]", dataType: "integer", table: "customer_data" },
          { id: "[Customer]", name: "[Customer]", dataType: "string", table: "customer_data" },
        ],
      },
      {
        id: "d_sales",
        name: "SalesDS",
        tables: [{ name: "sales_data" }],
        columns: [
          { id: "[CustomerKey]", name: "[CustomerKey]", dataType: "integer", table: "sales_data" },
          { id: "[DateKey]", name: "[DateKey]", dataType: "integer", table: "sales_data" },
          { id: "[ProductKey]", name: "[ProductKey]", dataType: "integer", table: "sales_data" },
          { id: "[SalesAmount]", name: "[SalesAmount]", dataType: "double", table: "sales_data" },
          { id: "[TotalCost]", name: "[TotalCost]", dataType: "double", table: "sales_data" },
        ],
      },
    ],
  };

  const spec = createAbstractSpecFromParsedWorkbook(workbook, "<workbook />", "fact.twb");
  assert.equal(spec.semantic_model.fact_table, "sales_data");
  assert.equal(spec.build_log.some((entry) => entry.message.includes("FIX_1_M_FACT_APPLIED")), true);
});

test("FIX4 transforme Measure Names en tuiles KPI card", () => {
  const workbook: ParsedWorkbook = {
    ...parsedWorkbook,
    worksheets: [
      {
        id: "kpi1",
        name: "CD_KPIs",
        rows: [":Measure Names"],
        cols: [],
        marks: ["text"],
        filters: [],
      },
    ],
    dashboards: [{ id: "db_kpi", name: "Customer Details", zones: [{ id: "1", name: "CD_KPIs" }] }],
  };

  const spec = createAbstractSpecFromParsedWorkbook(workbook, "<workbook />", "kpi.twb");
  const visuals = spec.dashboard_spec.pages[0]?.visuals ?? [];
  assert.equal(visuals.length, 4);
  assert.equal(visuals.every((visual) => visual.type === "card"), true);
});

test("FIX5 mappe les worksheets par zones dashboard sans dupliquer les pages", () => {
  const workbook: ParsedWorkbook = {
    ...parsedWorkbook,
    worksheets: [
      { id: "1", name: "CD_SalesbyCountry", rows: ["[Sales]"], cols: ["[Region]"], marks: ["map"], filters: [] },
      { id: "2", name: "PD_Matrix", rows: ["[Sales]"], cols: ["[Region]"], marks: ["text"], filters: [] },
      { id: "3", name: "SO_SalesProduct", rows: ["[Sales]"], cols: ["[Region]"], marks: ["bar"], filters: [] },
    ],
    dashboards: [
      {
        id: "db_customer",
        name: "Customer Details",
        zones: [{ id: "10", name: "CD_SalesbyCountry" }],
      },
      {
        id: "db_product",
        name: "Product Details",
        zones: [{ id: "20", name: "PD_Matrix" }],
      },
      {
        id: "db_sales",
        name: "Sales Overview",
        zones: [{ id: "30", name: "SO_SalesProduct" }],
      },
    ],
  };

  const spec = createAbstractSpecFromParsedWorkbook(workbook, "<workbook />", "zones.twb");
  assert.equal(spec.dashboard_spec.pages.length, 3);
  assert.equal(spec.dashboard_spec.pages[0]?.visuals.every((v) => v.source_worksheet.startsWith("CD_")), true);
  assert.equal(spec.dashboard_spec.pages[1]?.visuals.every((v) => v.source_worksheet.startsWith("PD_")), true);
  assert.equal(spec.dashboard_spec.pages[2]?.visuals.every((v) => v.source_worksheet.startsWith("SO_")), true);
});

test("FIX6 applique visual types PBI attendus", () => {
  const workbook: ParsedWorkbook = {
    ...parsedWorkbook,
    worksheets: [
      { id: "1", name: "SO_KPIs", rows: ["[Sales]"], cols: ["[Region]"], marks: ["text"], filters: [] },
      { id: "2", name: "SO_Sales vs Profit", rows: ["[Sales]"], cols: ["[Date]"], marks: ["line"], filters: [] },
      { id: "3", name: "SO_SalesCountry", rows: ["[Sales]"], cols: ["[Country]"], marks: ["map"], filters: [] },
      { id: "4", name: "PD_Matrix", rows: ["[Sales]"], cols: ["[Product]"], marks: ["texttable"], filters: [] },
      { id: "5", name: "SO_TopProduct", rows: ["[Sales]"], cols: ["[Product]"], marks: ["bar"], filters: [] },
    ],
    dashboards: [{ id: "db1", name: "Main Dashboard", zones: [] }],
  };

  const spec = createAbstractSpecFromParsedWorkbook(workbook, "<workbook />", "types.twb");
  const types = spec.dashboard_spec.pages[0]?.visuals.map((visual) => visual.type) ?? [];
  assert.equal(types.includes("card"), true);
  assert.equal(types.includes("lineChart"), true);
  assert.equal(types.includes("filledMap"), true);
  assert.equal(types.includes("tableEx"), true);
  assert.equal(types.includes("barChart"), true);
});
