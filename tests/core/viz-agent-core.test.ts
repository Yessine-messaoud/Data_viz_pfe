import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { VizAgentCore } from "../../src/core/viz-agent-core.js";

const twb = `<?xml version="1.0" encoding="utf-8"?>
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
        <relation name="sales_data" table="sales_data" />
      </connection>
      <column name="[Sales]" caption="Sales" datatype="real" table="sales_data" />
      <column name="[Region]" caption="Region" datatype="string" table="sales_data" />
    </datasource>
  </datasources>
</workbook>`;

test("viz agent core execute pipeline parse->semantic->spec->transform->export->lineage", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "coeur-core-"));
  const inputDir = path.join(root, "input");
  await mkdir(inputDir, { recursive: true });

  const workbookPath = path.join(inputDir, "sample.twb");
  await writeFile(workbookPath, twb, "utf8");

  const core = new VizAgentCore();
  const result = await core.run(workbookPath, root);

  assert.ok(result.artifact.endsWith(".pbix"));
  assert.equal(result.spec.export_manifest.target, "powerbi");
  assert.equal(result.lineage.sql_equivalents.length >= 1, true);

  await rm(root, { recursive: true, force: true });
});
