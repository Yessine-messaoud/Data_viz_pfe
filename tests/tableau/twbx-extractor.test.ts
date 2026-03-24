import test from "node:test";
import assert from "node:assert/strict";

import AdmZip from "adm-zip";

import { ZipTwbxExtractor } from "../../src/tableau/twbx-extractor.js";

test("extract .twbx archive avec .twb + data files", () => {
  const zip = new AdmZip();
  zip.addFile("workbook.twb", Buffer.from("<workbook />", "utf8"));
  zip.addFile("Data/sample.hyper", Buffer.from([1, 2, 3]));
  zip.addFile("Data/seed.csv", Buffer.from("a,b\n1,2", "utf8"));

  const extractor = new ZipTwbxExtractor();
  const result = extractor.extract(new Uint8Array(zip.toBuffer()));

  assert.equal(result.twbPath, "workbook.twb");
  assert.equal(result.twbContent, "<workbook />");
  assert.equal(result.dataFiles.length, 2);
  assert.ok(result.dataFiles.some((file) => file.type === "hyper"));
  assert.ok(result.dataFiles.some((file) => file.type === "csv"));
});
