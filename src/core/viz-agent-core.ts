import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { AdapterRegistry } from "../adapter/adapter-registry.js";
import { PowerBIAdapter } from "../adapter/powerbi-adapter.js";
import { writePaginatedRdl } from "../adapter/paginated-report-builder.js";
import type { AbstractSpec } from "../spec/abstract-spec.js";
import { AbstractSpecValidator } from "../spec/abstract-spec-validator.js";
import { buildLineageJson } from "../lineage/lineage-json-builder.js";
import type { LineageJson } from "../lineage/lineage-spec.js";
import {
  buildAbstractSpecPivot,
  runSemanticLayerFromParsedWorkbookHybrid,
} from "../demo/parsed-workbook-to-abstract.js";
import { XmlTableauParser } from "../tableau/tableau-parser.js";
import { ZipTwbxExtractor } from "../tableau/twbx-extractor.js";
import { DefaultTransformationEngine } from "../transform/transformation-engine.js";

export interface VizAgentRunOutput {
  artifact: string;
  spec: AbstractSpec;
  lineage: LineageJson;
  url?: string;
}

export interface VizAgentRunOptions {
  artifactTarget?: "pbix" | "rdl";
}

export class VizAgentCore {
  public async run(workbookPath: string, workspaceRoot: string, options: VizAgentRunOptions = {}): Promise<VizAgentRunOutput> {
    const artifactTarget = options.artifactTarget ?? "pbix";

    // Ordered pipeline: 1) Parse Tableau 2) Semantic Layer 3) Build AbstractSpec (pivot)
    const loaded = await this.loadWorkbook(workbookPath);
    const semanticLayer = await runSemanticLayerFromParsedWorkbookHybrid(loaded.parsedWorkbook, loaded.extraction);

    const initialSpec = buildAbstractSpecPivot(semanticLayer, loaded.workbookRaw, path.basename(workbookPath));

    const transformationEngine = new DefaultTransformationEngine();
    const transformed = transformationEngine.run(
      ["normalize schema", "add date dimension"],
      initialSpec.semantic_model,
      initialSpec.data_lineage,
    );

    const spec: AbstractSpec = {
      ...initialSpec,
      export_manifest: transformed.exportManifest,
    };

    const validator = new AbstractSpecValidator();
    const validation = validator.validate(spec);
    if (!validation.valid) {
      throw new Error(`Spec validation failed with ${validation.issueCount} issue(s).`);
    }

    const outputDir = path.join(workspaceRoot, "output");
    await mkdir(outputDir, { recursive: true });

    let artifact = "";
    let deployUrl: string | undefined;

    if (artifactTarget === "rdl") {
      artifact = await writePaginatedRdl(spec, outputDir);
    } else {
      const registry = new AdapterRegistry();
      registry.register("powerbi", new PowerBIAdapter());
      const adapter = registry.resolve(spec.export_manifest.target);

      const adapterValidation = adapter.validate(spec);
      if (!adapterValidation.valid) {
        throw new Error(`Adapter validation failed: ${adapterValidation.errors.join(" | ")}`);
      }

      const buildResult = await adapter.build(spec, outputDir);
      const deployResult = await adapter.deploy(buildResult);
      artifact = buildResult.artifactPath;
      deployUrl = deployResult.url;
    }

    const lineage = buildLineageJson(spec);
    await writeFile(path.join(outputDir, "lineage.json"), JSON.stringify(lineage, null, 2), "utf8");
    await writeFile(path.join(outputDir, "abstract-spec.json"), JSON.stringify(spec, null, 2), "utf8");

    const output: VizAgentRunOutput = {
      artifact,
      spec,
      lineage,
    };

    if (deployUrl !== undefined) {
      output.url = deployUrl;
    }

    return output;
  }

  private async loadWorkbook(filePath: string): Promise<{
    parsedWorkbook: ReturnType<XmlTableauParser["parseTwbXml"]>;
    workbookRaw: string | Uint8Array;
    extraction?: {
      twbContent: string;
      twbPath: string;
      dataFiles: Array<{ path: string; type: "hyper" | "csv" | "other"; bytes: Uint8Array }>;
    };
  }> {
    const parser = new XmlTableauParser();
    const bytes = await readFile(filePath);

    if (filePath.toLowerCase().endsWith(".twb")) {
      const xml = bytes.toString("utf8");
      return {
        parsedWorkbook: parser.parseTwbXml(xml),
        workbookRaw: xml,
      };
    }

    if (filePath.toLowerCase().endsWith(".twbx")) {
      const extractor = new ZipTwbxExtractor();
      const extracted = extractor.extract(new Uint8Array(bytes));
      return {
        parsedWorkbook: parser.parseTwbXml(extracted.twbContent),
        workbookRaw: new Uint8Array(bytes),
        extraction: extracted,
      };
    }

    throw new Error(`Unsupported workbook path: ${filePath}`);
  }
}
