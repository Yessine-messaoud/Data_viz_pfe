import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
export function readHyperTablesFromBytes(bytes, sourcePath) {
    const logs = [];
    const warnings = [];
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
        let payload;
        try {
            payload = JSON.parse(output);
        }
        catch {
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
    }
    finally {
        rmSync(tempDir, { recursive: true, force: true });
    }
}
