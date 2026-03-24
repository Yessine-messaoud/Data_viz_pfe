import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createAbstractSpecFromParsedWorkbookHybrid } from "./parsed-workbook-to-abstract.js";
import { XmlTableauParser } from "../tableau/tableau-parser.js";
import { ZipTwbxExtractor } from "../tableau/twbx-extractor.js";
import { AbstractSpecValidator } from "../spec/abstract-spec-validator.js";
function isWorkbookFile(fileName) {
    const lower = fileName.toLowerCase();
    return lower.endsWith(".twb") || lower.endsWith(".twbx");
}
async function resolveInputFolder(workspaceRoot) {
    const candidates = [path.join(workspaceRoot, "input"), path.join(workspaceRoot, "Input")];
    for (const candidate of candidates) {
        try {
            const stat = await readdir(candidate);
            if (stat.length >= 0) {
                return candidate;
            }
        }
        catch {
            // Continue scanning fallback path.
        }
    }
    throw new Error("No input folder found. Create input/ or Input/ with a .twb or .twbx file.");
}
async function loadWorkbook(filePath) {
    const parser = new XmlTableauParser();
    const fileBuffer = await readFile(filePath);
    const lower = filePath.toLowerCase();
    const workbookName = path.basename(filePath);
    if (lower.endsWith(".twb")) {
        const xml = fileBuffer.toString("utf8");
        return {
            parsedWorkbook: parser.parseTwbXml(xml),
            workbookRaw: xml,
            workbookName,
        };
    }
    if (lower.endsWith(".twbx")) {
        const extractor = new ZipTwbxExtractor();
        const extracted = extractor.extract(new Uint8Array(fileBuffer));
        return {
            parsedWorkbook: parser.parseTwbXml(extracted.twbContent),
            workbookRaw: new Uint8Array(fileBuffer),
            workbookName,
            extraction: extracted,
        };
    }
    throw new Error(`Unsupported workbook extension: ${filePath}`);
}
async function pickWorkbookFile(inputDir) {
    const entries = await readdir(inputDir, { withFileTypes: true });
    const workbook = entries.find((entry) => entry.isFile() && isWorkbookFile(entry.name));
    if (workbook === undefined) {
        throw new Error(`No .twb or .twbx file found in ${inputDir}`);
    }
    return path.join(inputDir, workbook.name);
}
export async function runAbstractVisualizationDemo(workspaceRoot) {
    const inputDir = await resolveInputFolder(workspaceRoot);
    const workbookPath = await pickWorkbookFile(inputDir);
    const loaded = await loadWorkbook(workbookPath);
    const spec = await createAbstractSpecFromParsedWorkbookHybrid(loaded.parsedWorkbook, loaded.workbookRaw, loaded.workbookName, loaded.extraction);
    const outputDir = path.join(workspaceRoot, "output");
    await mkdir(outputDir, { recursive: true });
    const validator = new AbstractSpecValidator();
    const report = validator.validate(spec);
    const reportPath = path.join(outputDir, "abstract-spec-validation-report.json");
    await writeFile(reportPath, JSON.stringify(report, null, 2), "utf8");
    if (!report.valid) {
        throw new Error(`AbstractSpec validation failed with ${report.issueCount} issue(s). See ${reportPath}`);
    }
    const outputPath = path.join(outputDir, "abstract-visualization.json");
    await writeFile(outputPath, JSON.stringify(spec, null, 2), "utf8");
    return outputPath;
}
async function main() {
    const workspaceRoot = process.cwd();
    const outputPath = await runAbstractVisualizationDemo(workspaceRoot);
    process.stdout.write(`Abstract visualization generated: ${outputPath}\n`);
}
const currentFile = fileURLToPath(import.meta.url);
const entryFile = process.argv[1];
if (entryFile !== undefined && path.resolve(entryFile) === path.resolve(currentFile)) {
    main().catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`Demo failed: ${message}\n`);
        process.exitCode = 1;
    });
}
