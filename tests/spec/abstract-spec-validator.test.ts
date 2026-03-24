import test from "node:test";
import assert from "node:assert/strict";

import { AbstractSpecValidator } from "../../src/spec/abstract-spec-validator.js";
import type { AbstractSpec } from "../../src/spec/abstract-spec.js";

const baseSpec: AbstractSpec = {
  id: "id-1",
  version: "0.1.0",
  source_fingerprint: "abc",
  dashboard_spec: {
    pages: [
      {
        id: "p1",
        name: "Page",
        visuals: [
          {
            id: "v1",
            source_worksheet: "Sheet1",
            type: "bar",
            position: { row: 0, column: 0, row_span: 1, column_span: 1 },
            data_binding: {
              axes: {
                x: { table: "unknown_table", column: "federated.abc.none:Category:nk" },
              },
            },
          },
        ],
      },
    ],
    global_filters: [],
    theme: { name: "t", palette: ["#000"] },
    refresh_policy: { mode: "manual" },
  },
  semantic_model: {
    entities: [],
    measures: [],
    dimensions: [],
    hierarchies: [],
    relationships: [],
    glossary: [],
    fact_table: "unknown_table",
    grain: "row",
  },
  data_lineage: {
    tables: [{ id: "t1", name: "unknown_table" }],
    joins: [],
    columns_used: [
      {
        visual_id: "v1",
        column: { table: "unknown_table", column: "federated.abc.none:Category:nk" },
        usage: "axis",
      },
    ],
    visual_column_map: {
      v1: {
        columns: [{ table: "unknown_table", column: "federated.abc.none:Category:nk" }],
        joins_used: [],
        filters: [],
      },
    },
  },
  export_manifest: {
    target: "powerbi",
    model_config: { dataset_name: "d" },
    dax_measures: [],
    m_queries: [],
    post_export_hooks: [],
  },
  build_log: [],
  warnings: [],
};

test("validator bloque unknown_table et tokens federated bruts", () => {
  const validator = new AbstractSpecValidator();
  const report = validator.validate(baseSpec);

  assert.equal(report.valid, false);
  assert.ok(report.issueCount >= 2);
  assert.ok(report.issues.some((issue) => issue.code === "UNKNOWN_TABLE"));
  assert.ok(report.issues.some((issue) => issue.code === "RAW_FEDERATED_TOKEN"));
});

test("validator bloque les visuels sans data binding", () => {
  const validator = new AbstractSpecValidator();
  const emptyBindingSpec: AbstractSpec = {
    ...baseSpec,
    dashboard_spec: {
      ...baseSpec.dashboard_spec,
      pages: [
        {
          ...baseSpec.dashboard_spec.pages[0]!,
          visuals: [
            {
              ...baseSpec.dashboard_spec.pages[0]!.visuals[0]!,
              data_binding: { axes: {} },
            },
          ],
        },
      ],
    },
  };

  const report = validator.validate(emptyBindingSpec);
  assert.equal(report.valid, false);
  assert.ok(report.issues.some((issue) => issue.code === "EMPTY_VISUAL_BINDING"));
});
