import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { runAbstractVisualizationDemo } from "../../src/demo/run-abstract-visualization-demo.js";

const simpleTwb = `<?xml version="1.0" encoding="utf-8"?>
<workbook>
  <worksheets>
    <worksheet name="Sheet1">
      <table>
        <rows>[Sales]</rows>
        <cols>[Region]</cols>
      </table>
      <panes>
        <mark>bar</mark>
      </panes>
    </worksheet>
  </worksheets>
  <datasources>
    <datasource name="ds1" caption="MainDS">
      <connection>
        <relation name="fact_sales" table="fact_sales" />
      </connection>
      <column name="[Sales]" caption="Sales" datatype="real" table="fact_sales" />
      <column name="[Region]" caption="Region" datatype="string" table="fact_sales" />
    </datasource>
  </datasources>
</workbook>`;

test("demo lit Input et ecrit output/abstract-visualization.json", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "coeur-demo-"));
  const inputDir = path.join(root, "Input");
  await mkdir(inputDir, { recursive: true });
  await writeFile(path.join(inputDir, "sample.twb"), simpleTwb, "utf8");

  const outputPath = await runAbstractVisualizationDemo(root);
  const outputRaw = await readFile(outputPath, "utf8");
  const reportRaw = await readFile(path.join(root, "output", "abstract-spec-validation-report.json"), "utf8");
  const json = JSON.parse(outputRaw) as { dashboard_spec?: { pages?: unknown[] } };
  const report = JSON.parse(reportRaw) as { valid?: boolean };

  assert.ok(outputPath.endsWith("abstract-visualization.json"));
  assert.equal(Array.isArray(json.dashboard_spec?.pages), true);
  assert.equal(report.valid, true);

  await rm(root, { recursive: true, force: true });
});
