import { readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { writePaginatedRdl } from "../adapter/paginated-report-builder.js";
import { VizAgentCore } from "../core/viz-agent-core.js";
import { readHyperTablesFromBytes } from "../tableau/hyper-api-reader.js";
import { ZipTwbxExtractor } from "../tableau/twbx-extractor.js";
import { runAbstractVisualizationDemo } from "./run-abstract-visualization-demo.js";
import { generateSimpleVisualFromAbstractJson } from "./generate-simple-visual.js";

function isWorkbookFile(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return lower.endsWith(".twb") || lower.endsWith(".twbx");
}

async function resolveInputFolder(workspaceRoot: string): Promise<string> {
  const candidates = [path.join(workspaceRoot, "input"), path.join(workspaceRoot, "Input")];
  for (const candidate of candidates) {
    try {
      const entries = await readdir(candidate);
      if (entries.length >= 0) {
        return candidate;
      }
    } catch {
      // Continue scanning fallback path.
    }
  }
  throw new Error("No input folder found. Create input/ or Input/ with a .twb or .twbx file.");
}

async function pickWorkbookFile(inputDir: string): Promise<string> {
  const entries = await readdir(inputDir, { withFileTypes: true });
  const workbook = entries.find((entry) => entry.isFile() && isWorkbookFile(entry.name));
  if (workbook === undefined) {
    throw new Error(`No .twb or .twbx file found in ${inputDir}`);
  }
  return path.join(inputDir, workbook.name);
}

export interface FullPipelineDemoOutput {
  abstractJsonPath: string;
  visualHtmlPath: string;
  artifactPath: string;
  lineagePath: string;
  abstractSpecPath: string;
  paginatedRdlPath: string;
  extractionProofPath: string;
  pbixPath?: string;
  deployUrl?: string;
}

interface TwbxExtractionProofFile {
  inputWorkbook: string;
  mode: "twbx" | "twb";
  hyperExtracted: boolean;
  twbPath?: string;
  dataFiles: Array<{
    path: string;
    type: "hyper" | "csv" | "other";
    sizeBytes: number;
    head5: string[];
  }>;
  notes: string[];
}

function toHead5BytesHex(bytes: Uint8Array): string[] {
  const first = Array.from(bytes.slice(0, 5));
  return first.map((value, index) => `byte${index + 1}: 0x${value.toString(16).padStart(2, "0")}`);
}

function toHead5Lines(bytes: Uint8Array): string[] {
  const text = Buffer.from(bytes).toString("utf8");
  return text.split(/\r?\n/).slice(0, 5);
}

async function writeExtractionProof(workbookPath: string, workspaceRoot: string): Promise<string> {
  const outputPath = path.join(workspaceRoot, "output", "twbx-extraction-proof.json");
  const lower = workbookPath.toLowerCase();

  if (lower.endsWith(".twb")) {
    const proof: TwbxExtractionProofFile = {
      inputWorkbook: path.basename(workbookPath),
      mode: "twb",
      hyperExtracted: false,
      dataFiles: [],
      notes: ["Input is .twb (plain XML). No embedded data archive to extract."],
    };
    await writeFile(outputPath, JSON.stringify(proof, null, 2), "utf8");
    return outputPath;
  }

  const bytes = await readFile(workbookPath);
  const extractor = new ZipTwbxExtractor();
  const extracted = extractor.extract(new Uint8Array(bytes));

  const proof: TwbxExtractionProofFile = {
    inputWorkbook: path.basename(workbookPath),
    mode: "twbx",
    hyperExtracted: extracted.dataFiles.some((file) => file.type === "hyper"),
    twbPath: extracted.twbPath,
    dataFiles: extracted.dataFiles.map((file) => ({
      ...(() => {
        if (file.type === "hyper") {
          const hyperRead = readHyperTablesFromBytes(file.bytes, file.path);
          const firstTable = hyperRead.tables[0];
          if (firstTable !== undefined) {
            return {
              path: file.path,
              type: file.type,
              sizeBytes: file.bytes.length,
              head5: firstTable.sample_data.slice(0, 5).map((row) => JSON.stringify(row)),
            };
          }
        }

        return {
          path: file.path,
          type: file.type,
          sizeBytes: file.bytes.length,
          head5: file.type === "csv" ? toHead5Lines(file.bytes) : toHead5BytesHex(file.bytes),
        };
      })(),
    })),
    notes: [
      "For binary files (.hyper/.other), head(5) is displayed as first 5 bytes in hex.",
      "For .csv files, head(5) is displayed as first 5 lines.",
    ],
  };

  await writeFile(outputPath, JSON.stringify(proof, null, 2), "utf8");
  return outputPath;
}

export async function runFullPipelineDemo(workspaceRoot: string): Promise<FullPipelineDemoOutput> {
  const abstractJsonPath = await runAbstractVisualizationDemo(workspaceRoot);

  const inputDir = await resolveInputFolder(workspaceRoot);
  const workbookPath = await pickWorkbookFile(inputDir);
  const extractionProofPath = await writeExtractionProof(workbookPath, workspaceRoot);

  const core = new VizAgentCore();
  const runResult = await core.run(workbookPath, workspaceRoot, { artifactTarget: "rdl" });

  // Keep abstract-visualization aligned with the final transformed spec used for export.
  await writeFile(abstractJsonPath, JSON.stringify(runResult.spec, null, 2), "utf8");

  const paginatedRdlPath = runResult.artifact.endsWith(".rdl")
    ? runResult.artifact
    : await writePaginatedRdl(runResult.spec, path.join(workspaceRoot, "output"));
  const visualHtmlPath = await generateSimpleVisualFromAbstractJson(workspaceRoot);

  const output: FullPipelineDemoOutput = {
    abstractJsonPath,
    visualHtmlPath,
    artifactPath: paginatedRdlPath,
    lineagePath: path.join(workspaceRoot, "output", "lineage.json"),
    abstractSpecPath: path.join(workspaceRoot, "output", "abstract-spec.json"),
    paginatedRdlPath,
    extractionProofPath,
  };

  if (runResult.artifact.toLowerCase().endsWith(".pbix")) {
    output.pbixPath = runResult.artifact;
  }

  if (runResult.url !== undefined) {
    output.deployUrl = runResult.url;
  }

  return output;
}

async function main(): Promise<void> {
  const result = await runFullPipelineDemo(process.cwd());
  process.stdout.write(`Full pipeline demo generated:\n`);
  process.stdout.write(`- Abstract JSON: ${result.abstractJsonPath}\n`);
  process.stdout.write(`- Visual HTML: ${result.visualHtmlPath}\n`);
  process.stdout.write(`- Target artifact (RDL): ${result.artifactPath}\n`);
  if (result.pbixPath !== undefined) {
    process.stdout.write(`- PBIX artifact: ${result.pbixPath}\n`);
  }
  process.stdout.write(`- Abstract spec: ${result.abstractSpecPath}\n`);
  process.stdout.write(`- Lineage JSON: ${result.lineagePath}\n`);
  process.stdout.write(`- Extraction proof JSON: ${result.extractionProofPath}\n`);
  process.stdout.write(`- Paginated report (RDL): ${result.paginatedRdlPath}\n`);
  if (result.deployUrl !== undefined) {
    process.stdout.write(`- Deploy URL: ${result.deployUrl}\n`);
  }
}

const currentFile = fileURLToPath(import.meta.url);
const entryFile = process.argv[1];
if (entryFile !== undefined && path.resolve(entryFile) === path.resolve(currentFile)) {
  main().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Full demo failed: ${message}\n`);
    process.exitCode = 1;
  });
}
