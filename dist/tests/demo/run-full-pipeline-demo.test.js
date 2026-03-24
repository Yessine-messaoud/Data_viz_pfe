import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { runFullPipelineDemo } from "../../src/demo/run-full-pipeline-demo.js";
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
test("runFullPipelineDemo genere json/html/rdl/lineage/spec", async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), "coeur-full-demo-"));
    const inputDir = path.join(root, "Input");
    await mkdir(inputDir, { recursive: true });
    await writeFile(path.join(inputDir, "sample.twb"), twb, "utf8");
    const result = await runFullPipelineDemo(root);
    assert.ok(result.abstractJsonPath.endsWith("abstract-visualization.json"));
    assert.ok(result.visualHtmlPath.endsWith("abstract-visualization.html"));
    assert.ok(result.artifactPath.endsWith(".rdl"));
    assert.ok(result.lineagePath.endsWith("lineage.json"));
    assert.ok(result.abstractSpecPath.endsWith("abstract-spec.json"));
    assert.ok(result.extractionProofPath.endsWith("twbx-extraction-proof.json"));
    assert.ok(result.paginatedRdlPath.endsWith("powerbi-paginated-report.rdl"));
    const rdlContent = await readFile(result.paginatedRdlPath, "utf8");
    const proofRaw = await readFile(result.extractionProofPath, "utf8");
    const proof = JSON.parse(proofRaw);
    assert.ok(rdlContent.includes("<Report "));
    assert.equal(proof.mode, "twb");
    assert.equal((proof.notes?.length ?? 0) > 0, true);
    await rm(root, { recursive: true, force: true });
});
test("runFullPipelineDemo genere une preuve d'extraction hyper avec head(5) pour un twbx", async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), "coeur-full-demo-twbx-"));
    const inputDir = path.join(root, "Input");
    await mkdir(inputDir, { recursive: true });
    const zip = new AdmZip();
    zip.addFile("workbook.twb", Buffer.from(twb, "utf8"));
    zip.addFile("Data/fact.hyper", Buffer.from([1, 2, 3, 4, 5, 6, 7]));
    zip.addFile("Data/seed.csv", Buffer.from("a,b\n1,2\n3,4\n5,6\n7,8\n9,10", "utf8"));
    await writeFile(path.join(inputDir, "sample.twbx"), zip.toBuffer());
    const result = await runFullPipelineDemo(root);
    const proofRaw = await readFile(result.extractionProofPath, "utf8");
    const proof = JSON.parse(proofRaw);
    assert.equal(proof.mode, "twbx");
    assert.equal(proof.hyperExtracted, true);
    assert.equal((proof.dataFiles ?? []).some((file) => file.type === "hyper" && (file.head5?.length ?? 0) === 5), true);
    await rm(root, { recursive: true, force: true });
});
