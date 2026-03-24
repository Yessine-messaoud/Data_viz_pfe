import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

export interface HyperColumnProfile {
  name: string;
  type: string;
}

export interface HyperTableProfile {
  table_name: string;
  columns: HyperColumnProfile[];
  sample_data: Array<Record<string, string | number | boolean | null>>;
  source: "hyper";
}

export interface HyperApiReadResult {
  tables: HyperTableProfile[];
  logs: string[];
  warnings: string[];
}

interface HyperQueryPayload {
  ok: boolean;
  error?: string;
  tables?: HyperTableProfile[];
}

export function readHyperTablesFromBytes(bytes: Uint8Array, sourcePath: string): HyperApiReadResult {
  const logs: string[] = [];
  const warnings: string[] = [];

  const python = process.env.HYPERAPI_PYTHON ?? "python";
  const scriptPath = path.join(process.cwd(), "src", "tableau", "hyper-query.py");
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "coeur-hyper-"));

  try {
    const fileName = path.basename(sourcePath) || "extract.hyper";
    const tempFile = path.join(tempDir, fileName.toLowerCase().endsWith(".hyper") ? fileName : `${fileName}.hyper`);
    writeFileSync(tempFile, Buffer.from(bytes));

    const child = spawnSync(python, [scriptPath, tempFile, "--head", "5"], {
      encoding: "utf8",
      windowsHide: true,
    });

    if (child.error !== undefined) {
      warnings.push(`WARN_HYPERAPI_EXEC_FAILED:${String(child.error.message ?? child.error)}`);
      return { tables: [], logs, warnings };
    }

    const output = (child.stdout ?? "").trim();
    if (output.length === 0) {
      warnings.push("WARN_HYPERAPI_EMPTY_OUTPUT:No output from hyper query process");
      return { tables: [], logs, warnings };
    }

    let payload: HyperQueryPayload;
    try {
      payload = JSON.parse(output) as HyperQueryPayload;
    } catch {
      warnings.push("WARN_HYPERAPI_INVALID_JSON:Unable to parse hyper query output");
      return { tables: [], logs, warnings };
    }

    if (!payload.ok) {
      warnings.push(`WARN_HYPERAPI_QUERY_FAILED:${payload.error ?? "unknown error"}`);
      return { tables: [], logs, warnings };
    }

    const tables = payload.tables ?? [];
    logs.push(`hyperapi tables detected: ${tables.length}`);
    return { tables, logs, warnings };
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}
