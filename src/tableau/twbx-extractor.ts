import AdmZip from "adm-zip";

import type { TwbxExtractionResult, TwbxExtractor } from "./interfaces.js";

function detectFileType(path: string): "hyper" | "csv" | "other" {
  const lower = path.toLowerCase();
  if (lower.endsWith(".hyper")) {
    return "hyper";
  }
  if (lower.endsWith(".csv")) {
    return "csv";
  }
  return "other";
}

export class ZipTwbxExtractor implements TwbxExtractor {
  public extract(buffer: Uint8Array): TwbxExtractionResult {
    const zip = new AdmZip(Buffer.from(buffer));
    const entries = zip.getEntries();

    const twbEntry = entries.find((entry) => entry.entryName.toLowerCase().endsWith(".twb"));
    if (twbEntry === undefined) {
      throw new Error("Invalid TWBX archive: no .twb file found");
    }

    const twbContent = twbEntry.getData().toString("utf8");
    const dataFiles = entries
      .filter((entry) => !entry.isDirectory)
      .filter((entry) => entry.entryName !== twbEntry.entryName)
      .map((entry) => ({
        path: entry.entryName,
        type: detectFileType(entry.entryName),
        bytes: new Uint8Array(entry.getData()),
      }));

    return {
      twbContent,
      twbPath: twbEntry.entryName,
      dataFiles,
    };
  }
}
