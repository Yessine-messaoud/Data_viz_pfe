import { mkdir, readFile, readdir, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import type { AbstractSpec } from "../spec/abstract-spec.js";

interface LayerStatus {
  layer: string;
  status: "PASS" | "WARN";
  evidence: string;
}

interface ArtifactStatus {
  name: string;
  status: "present" | "missing" | "optional";
  sizeBytes?: number;
}

interface ExtractionProofFile {
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

interface ProofReport {
  generatedAt: string;
  layerStatuses: LayerStatus[];
  artifacts: ArtifactStatus[];
  extractionProof?: ExtractionProofFile;
}

interface LlmRuntimeStatus {
  semanticMode: string;
  semanticCalled: boolean;
  semanticSuggestions: number;
  calcCalls: number;
  calcSuccess: number;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderVisualList(spec: AbstractSpec): string {
  return spec.dashboard_spec.pages
    .map((page) => {
      const visualItems = page.visuals
        .map((visual) => {
          const axes = visual.data_binding.axes;
          const axisEntries = [
            axes.x ? `x: ${axes.x.column}` : "",
            axes.y ? `y: ${axes.y.column}` : "",
            axes.color ? `color: ${axes.color.column}` : "",
            axes.size ? `size: ${axes.size.column}` : "",
            axes.tooltip ? `tooltip: ${axes.tooltip.column}` : "",
          ].filter((entry) => entry.length > 0);

          return `
            <li class="visual-item">
              <h4>${escapeHtml(visual.title ?? visual.id)}</h4>
              <p><strong>Type:</strong> ${escapeHtml(visual.type)}</p>
              <p><strong>Worksheet:</strong> ${escapeHtml(visual.source_worksheet)}</p>
              <p><strong>Bindings:</strong> ${escapeHtml(axisEntries.join(" | ") || "none")}</p>
            </li>
          `;
        })
        .join("\n");

      return `
        <section class="page-section">
          <h3>${escapeHtml(page.name)}</h3>
          <ul class="visual-list">
            ${visualItems}
          </ul>
        </section>
      `;
    })
    .join("\n");
}

export function createTablePreviewHTML(
  tables: Array<{
    name: string;
    source?: string;
    columns: Array<{ name: string; type: string }>;
    rows: Array<Record<string, string | number | boolean | null>>;
  }>,
): string {
  return tables
    .map((table) => {
      const rows = table.rows.slice(0, 5);
      const columnNames = table.columns.length > 0 ? table.columns.map((column) => column.name) : Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
      const columnSummary =
        table.columns.length > 0
          ? table.columns.map((column) => `${column.name}:${column.type}`).join(", ")
          : "No column metadata available";

      const header =
        columnNames.length > 0
          ? `<tr>${columnNames.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>`
          : "<tr><th>No columns available</th></tr>";

      const body =
        rows.length > 0
          ? rows
              .map(
                (row) =>
                  `<tr>${
                    columnNames.length > 0
                      ? columnNames.map((column) => `<td>${escapeHtml(String(row[column] ?? ""))}</td>`).join("")
                      : `<td>${escapeHtml(JSON.stringify(row))}</td>`
                  }</tr>`,
              )
              .join("\n")
          : `<tr><td colspan="${Math.max(columnNames.length, 1)}">No sample rows available</td></tr>`;

      return `
        <article class="panel table-preview-panel">
          <h3>TABLE: ${escapeHtml(table.name)}</h3>
          <p><strong>Source:</strong> ${escapeHtml(table.source ?? "unknown")}</p>
          <p><strong>Columns:</strong> ${escapeHtml(columnSummary)}</p>
          <div class="table-wrap">
            <table class="proof-table">
              <thead>${header}</thead>
              <tbody>${body}</tbody>
            </table>
          </div>
        </article>
      `;
    })
    .join("\n");
}

function renderSchemaGraph(spec: AbstractSpec): string {
  const profileNames = (spec.data_lineage.full_table_profiles ?? [])
    .slice()
    .sort((a, b) => {
      const ah = a.source === "hyper" ? 0 : 1;
      const bh = b.source === "hyper" ? 0 : 1;
      return ah - bh;
    })
    .map((profile) => profile.table_name);
  const tableNames =
    profileNames.length > 0
      ? profileNames
      : (spec.data_lineage.full_tables ?? spec.data_lineage.tables).map((table) => table.name);
  const fallback = spec.semantic_model.fact_table.length > 0 ? [spec.semantic_model.fact_table] : ["unknown_fact"];
  const nodes = (tableNames.length > 0 ? tableNames : fallback).slice(0, 8);

  const nodeWidth = 160;
  const nodeHeight = 42;
  const startX = 30;
  const startY = 28;
  const spacingX = 185;
  const spacingY = 90;

  const positions = new Map<string, { x: number; y: number }>();
  nodes.forEach((name, index) => {
    const col = index % 4;
    const row = Math.floor(index / 4);
    positions.set(name, { x: startX + col * spacingX, y: startY + row * spacingY });
  });

  const rects = nodes
    .map((name) => {
      const pos = positions.get(name);
      if (pos === undefined) {
        return "";
      }
      return `
        <rect x="${pos.x}" y="${pos.y}" width="${nodeWidth}" height="${nodeHeight}" rx="10" fill="#fff8ee" stroke="#cc9a62" stroke-width="1.5"></rect>
        <text x="${pos.x + 10}" y="${pos.y + 24}" fill="#1e2a32" font-size="12" font-family="Segoe UI, Tahoma, sans-serif">${escapeHtml(name)}</text>
      `;
    })
    .join("\n");

  const lines = spec.data_lineage.joins
    .slice(0, 12)
    .map((join) => {
      const left = positions.get(join.left_table);
      const right = positions.get(join.right_table);
      if (left === undefined || right === undefined) {
        return "";
      }
      const x1 = left.x + nodeWidth;
      const y1 = left.y + nodeHeight / 2;
      const x2 = right.x;
      const y2 = right.y + nodeHeight / 2;
      return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#1f6f8b" stroke-width="1.6" marker-end="url(#arrow)" />`;
    })
    .join("\n");

  const svgHeight = nodes.length > 4 ? 230 : 140;
  return `
    <svg viewBox="0 0 820 ${svgHeight}" role="img" aria-label="Schema graph" class="schema-svg">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#1f6f8b"></path>
        </marker>
      </defs>
      ${lines}
      ${rects}
    </svg>
  `;
}

function buildLayerEvidenceBlocks(spec: AbstractSpec): ReadonlyArray<readonly [string, unknown]> {
  const worksheets = Array.from(new Set(spec.dashboard_spec.pages.flatMap((page) => page.visuals.map((visual) => visual.source_worksheet))));
  const parseEvidence = {
    worksheets: worksheets.slice(0, 12),
    dashboard_pages: spec.dashboard_spec.pages.map((page) => page.name),
    visuals_detected: spec.dashboard_spec.pages.reduce((acc, page) => acc + page.visuals.length, 0),
  };

  const semanticEvidence = {
    fact_table: spec.semantic_model.fact_table,
    grain: spec.semantic_model.grain,
    measures_sample: spec.semantic_model.measures.slice(0, 6).map((measure) => measure.name),
    dimensions_sample: spec.semantic_model.dimensions.slice(0, 6).map((dimension) => dimension.name),
  };

  const abstractEvidence = {
    id: spec.id,
    version: spec.version,
    source_fingerprint_prefix: spec.source_fingerprint.slice(0, 16),
    warnings: spec.warnings.length,
  };

  const transformEvidence = {
    m_queries: spec.export_manifest.m_queries.slice(0, 6).map((query) => query.name),
    dax_measures: spec.export_manifest.dax_measures.slice(0, 6).map((measure) => measure.name),
  };

  const exportEvidence = {
    target: spec.export_manifest.target,
    dataset_name: spec.export_manifest.model_config.dataset_name,
    post_export_hooks: spec.export_manifest.post_export_hooks.map((hook) => hook.name),
  };

  const firstVisualLineage = Object.entries(spec.data_lineage.visual_column_map)[0];
  const lineageEvidence = {
    tables: spec.data_lineage.tables.slice(0, 8).map((table) => table.name),
    joins: spec.data_lineage.joins.slice(0, 6).map((join) => join.id),
    columns_used: spec.data_lineage.columns_used.length,
    sample_visual: firstVisualLineage?.[0] ?? null,
    sample_columns: firstVisualLineage?.[1].columns.map((column) => `${column.table}.${column.column}`).slice(0, 8) ?? [],
  };

  const blocks = [
    ["1) Parse Tableau", parseEvidence],
    ["2) Semantic Layer", semanticEvidence],
    ["3) Build AbstractSpec (pivot)", abstractEvidence],
    ["4) Transformation engine", transformEvidence],
    ["5) Export adapter", exportEvidence],
    ["6) Lineage & SQL generation", lineageEvidence],
  ] as const;

  return blocks;
}

function renderLayerEvidence(spec: AbstractSpec): string {
  const blocks = buildLayerEvidenceBlocks(spec);
  return blocks
    .map(([title, payload]) => {
      return `
        <article class="panel evidence-panel">
          <h3>${escapeHtml(title)}</h3>
          <pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
        </article>
      `;
    })
    .join("\n");
}

function renderPipelineStepStatus(spec: AbstractSpec, proof: ProofReport): string {
  const evidenceMap = new Map(buildLayerEvidenceBlocks(spec));
  const statusMap = new Map(proof.layerStatuses.map((status) => [status.layer, status]));

  const orderedSteps = [
    "1) Parse Tableau",
    "2) Semantic Layer",
    "3) Build AbstractSpec (pivot)",
    "4) Transformation engine",
    "5) Export adapter",
    "6) Lineage & SQL generation",
    "7) LLM Calc Translation",
  ];

  return orderedSteps
    .map((stepName) => {
      const status = statusMap.get(stepName);
      const statusText = status?.status ?? "WARN";
      const statusEvidence = status?.evidence ?? "No status evidence";
      const statusBadgeClass = statusText === "PASS" ? "badge-pass" : "badge-warn";
      const samplePayload =
        stepName === "7) LLM Calc Translation"
          ? { note: "Runtime counters are available in 'LLM Runtime Status'." }
          : (evidenceMap.get(stepName) ?? { note: "No sample output available." });

      return `
        <article class="panel pipeline-step-panel">
          <div class="pipeline-step-head">
            <h3>${escapeHtml(stepName)}</h3>
            <span class="badge ${statusBadgeClass}">${escapeHtml(statusText)}</span>
          </div>
          <p class="pipeline-step-evidence"><strong>Status evidence:</strong> ${escapeHtml(statusEvidence)}</p>
          <p class="pipeline-step-sample-title">Output sample</p>
          <pre>${escapeHtml(JSON.stringify(samplePayload, null, 2))}</pre>
        </article>
      `;
    })
    .join("\n");
}

function renderDatasourceTablePreview(spec: AbstractSpec): string {
  const profiles = spec.data_lineage.full_table_profiles ?? [];
  const sampledRows = spec.data_lineage.sampled_rows ?? {};

  const tableItems =
    profiles.length > 0
      ? profiles.map((profile) => ({
          name: profile.table_name,
          source: profile.source,
          columns: profile.columns,
          rows: profile.sample_data,
        }))
      : (spec.data_lineage.full_tables ?? spec.data_lineage.tables).map((table) => ({
          name: table.name,
          source: "unknown",
          columns: [],
          rows: sampledRows[table.name] ?? [],
        }));

  if (tableItems.length === 0) {
    return `<p>No datasource tables detected.</p>`;
  }

  return createTablePreviewHTML(tableItems);
}

function parseLlmRuntimeStatus(spec: AbstractSpec): LlmRuntimeStatus {
  const messageByKey = new Map<string, string>();
  for (const entry of spec.build_log) {
    const raw = entry.message;
    const idx = raw.indexOf("=");
    if (idx <= 0) {
      continue;
    }
    const key = raw.slice(0, idx).trim();
    const value = raw.slice(idx + 1).trim();
    messageByKey.set(key, value);
  }

  const semanticMode = messageByKey.get("semantic_enrichment_mode") ?? "unknown";
  const semanticCalled = (messageByKey.get("semantic_llm_called") ?? "false").toLowerCase() === "true";
  const semanticSuggestions = Number(messageByKey.get("semantic_llm_suggestions") ?? "0");
  const calcCalls = Number(messageByKey.get("calc_translation_llm_calls") ?? "0");
  const calcSuccess = Number(messageByKey.get("calc_translation_llm_success") ?? "0");

  return {
    semanticMode,
    semanticCalled,
    semanticSuggestions: Number.isFinite(semanticSuggestions) ? semanticSuggestions : 0,
    calcCalls: Number.isFinite(calcCalls) ? calcCalls : 0,
    calcSuccess: Number.isFinite(calcSuccess) ? calcSuccess : 0,
  };
}

function computeLayerStatuses(spec: AbstractSpec): LayerStatus[] {
  const llm = parseLlmRuntimeStatus(spec);

  const parseWorksheets = new Set(spec.dashboard_spec.pages.flatMap((page) => page.visuals.map((visual) => visual.source_worksheet)));
  const parseStatus: LayerStatus = {
    layer: "1) Parse Tableau",
    status: parseWorksheets.size > 0 ? "PASS" : "WARN",
    evidence: `${parseWorksheets.size} worksheet(s), ${spec.dashboard_spec.pages.length} page(s)`,
  };

  const semanticReady = spec.semantic_model.fact_table.length > 0 && spec.data_lineage.tables.length > 0;
  const semanticStatus: LayerStatus = {
    layer: "2) Semantic Layer",
    status: semanticReady ? "PASS" : "WARN",
    evidence: `fact_table=${spec.semantic_model.fact_table}, lineage_tables=${spec.data_lineage.tables.length}, llm_called=${llm.semanticCalled}, mode=${llm.semanticMode}, suggestions=${llm.semanticSuggestions}`,
  };

  const abstractStatus: LayerStatus = {
    layer: "3) Build AbstractSpec (pivot)",
    status: spec.id.length > 0 && spec.version.length > 0 ? "PASS" : "WARN",
    evidence: `id=${spec.id.slice(0, 8)}..., version=${spec.version}`,
  };

  const transformReady = spec.export_manifest.m_queries.length > 0 || spec.export_manifest.dax_measures.length > 0;
  const transformStatus: LayerStatus = {
    layer: "4) Transformation engine",
    status: transformReady ? "PASS" : "WARN",
    evidence: `m_queries=${spec.export_manifest.m_queries.length}, dax_measures=${spec.export_manifest.dax_measures.length}`,
  };

  const exportStatus: LayerStatus = {
    layer: "5) Export adapter",
    status: spec.export_manifest.target === "powerbi" ? "PASS" : "WARN",
    evidence: `target=${spec.export_manifest.target}, dataset=${spec.export_manifest.model_config.dataset_name}`,
  };

  const lineageReady = spec.data_lineage.columns_used.length > 0 || Object.keys(spec.data_lineage.visual_column_map).length > 0;
  const lineageStatus: LayerStatus = {
    layer: "6) Lineage & SQL generation",
    status: lineageReady ? "PASS" : "WARN",
    evidence: `columns_used=${spec.data_lineage.columns_used.length}, visuals_in_map=${Object.keys(spec.data_lineage.visual_column_map).length}`,
  };

  const calcLlmStatus: LayerStatus = {
    layer: "7) LLM Calc Translation",
    status: llm.calcCalls === 0 || llm.calcSuccess > 0 ? "PASS" : "WARN",
    evidence: `llm_calls=${llm.calcCalls}, success=${llm.calcSuccess}`,
  };

  return [parseStatus, semanticStatus, abstractStatus, transformStatus, exportStatus, lineageStatus, calcLlmStatus];
}

async function collectArtifactStatuses(outputDir: string): Promise<ArtifactStatus[]> {
  const artifacts: ArtifactStatus[] = [];
  const expected = [
    "abstract-visualization.json",
    "abstract-visualization.html",
    "abstract-spec.json",
    "lineage.json",
    "powerbi-paginated-report.rdl",
  ];

  for (const name of expected) {
    const filePath = path.join(outputDir, name);
    try {
      const info = await stat(filePath);
      artifacts.push({ name, status: "present", sizeBytes: info.size });
    } catch {
      artifacts.push({ name, status: "missing" });
    }
  }

  const rdlPresent = artifacts.some((artifact) => artifact.name.endsWith(".rdl") && artifact.status === "present");

  let pbixPresent = false;
  try {
    const entries = await readdir(outputDir);
    for (const entry of entries) {
      if (entry.endsWith(".pbix")) {
        const info = await stat(path.join(outputDir, entry));
        artifacts.push({ name: entry, status: "present", sizeBytes: info.size });
        pbixPresent = true;
        break;
      }
    }
  } catch {
    // Ignore directory reading failures for proof report.
  }

  if (!pbixPresent) {
    artifacts.push({ name: "artifact-*.pbix", status: rdlPresent ? "optional" : "missing" });
  }

  return artifacts;
}

async function loadExtractionProof(outputDir: string): Promise<ExtractionProofFile | undefined> {
  const filePath = path.join(outputDir, "twbx-extraction-proof.json");
  try {
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as ExtractionProofFile;
  } catch {
    return undefined;
  }
}

function renderExtractionProof(extractionProof?: ExtractionProofFile): string {
  if (extractionProof === undefined) {
    return `
      <h3>TWBX/HYPER Extraction Proof</h3>
      <p>No extraction proof file found. Run full pipeline to generate <code>output/twbx-extraction-proof.json</code>.</p>
    `;
  }

  const rows = extractionProof.dataFiles
    .map((file) => {
      return `
        <tr>
          <td>${escapeHtml(file.path)}</td>
          <td>${escapeHtml(file.type)}</td>
          <td>${file.sizeBytes} bytes</td>
          <td><pre>${escapeHtml(file.head5.join("\n"))}</pre></td>
        </tr>
      `;
    })
    .join("\n");

  const notes = extractionProof.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("\n");

  return `
    <h3>TWBX/HYPER Extraction Proof</h3>
    <p><strong>Input workbook:</strong> ${escapeHtml(extractionProof.inputWorkbook)}</p>
    <p><strong>Mode:</strong> ${escapeHtml(extractionProof.mode)} | <strong>Hyper extracted:</strong> ${extractionProof.hyperExtracted ? "YES" : "NO"}</p>
    <div class="table-wrap">
      <table class="proof-table">
        <thead>
          <tr><th>File</th><th>Type</th><th>Size</th><th>head(5)</th></tr>
        </thead>
        <tbody>
          ${rows.length > 0 ? rows : `<tr><td colspan="4">No embedded data files detected.</td></tr>`}
        </tbody>
      </table>
    </div>
    <ul class="proof-notes">
      ${notes}
    </ul>
  `;
}

function renderProofReport(proof: ProofReport): string {
  const layerRows = proof.layerStatuses
    .map((item) => {
      const badgeClass = item.status === "PASS" ? "badge-pass" : "badge-warn";
      return `
        <tr>
          <td>${escapeHtml(item.layer)}</td>
          <td><span class="badge ${badgeClass}">${item.status}</span></td>
          <td>${escapeHtml(item.evidence)}</td>
        </tr>
      `;
    })
    .join("\n");

  const targetArtifact = proof.artifacts.some((artifact) => artifact.name.endsWith(".rdl") && artifact.status === "present")
    ? "RDL"
    : proof.artifacts.some((artifact) => artifact.name.endsWith(".pbix") && artifact.status === "present")
      ? "PBIX"
      : "UNKNOWN";

  const artifactRows = proof.artifacts
    .map((artifact) => {
      const badgeClass = artifact.status === "present" ? "badge-pass" : artifact.status === "optional" ? "badge-info" : "badge-warn";
      const size = artifact.sizeBytes === undefined ? "-" : `${artifact.sizeBytes} bytes`;
      const statusLabel = artifact.status === "optional" ? "OPTIONAL" : artifact.status.toUpperCase();
      return `
        <tr>
          <td>${escapeHtml(artifact.name)}</td>
          <td><span class="badge ${badgeClass}">${statusLabel}</span></td>
          <td>${escapeHtml(size)}</td>
        </tr>
      `;
    })
    .join("\n");

  return `
    <section class="panel">
      <h2>Proof Report</h2>
      <p><strong>Generated at:</strong> ${escapeHtml(proof.generatedAt)}</p>
      <p><strong>Target artifact:</strong> ${escapeHtml(targetArtifact)}</p>
      <p><strong>Pipeline:</strong> 1) Parse Tableau -> 2) Semantic Layer -> 3) Build AbstractSpec (pivot) -> 4) Transformation engine -> 5) Export adapter -> 6) Lineage & SQL generation</p>

      <h3>Layer Status</h3>
      <div class="table-wrap">
        <table class="proof-table">
          <thead>
            <tr><th>Layer</th><th>Status</th><th>Evidence</th></tr>
          </thead>
          <tbody>
            ${layerRows}
          </tbody>
        </table>
      </div>

      <h3>Artifact Status</h3>
      <div class="table-wrap">
        <table class="proof-table">
          <thead>
            <tr><th>Artifact</th><th>Status</th><th>Size</th></tr>
          </thead>
          <tbody>
            ${artifactRows}
          </tbody>
        </table>
      </div>

      ${renderExtractionProof(proof.extractionProof)}
    </section>
  `;
}

function renderLlmStatusPanel(spec: AbstractSpec): string {
  const llm = parseLlmRuntimeStatus(spec);
  const semanticBadge = llm.semanticCalled ? "badge-pass" : "badge-warn";
  const calcBadge = llm.calcCalls === 0 || llm.calcSuccess > 0 ? "badge-pass" : "badge-warn";

  return `
    <section class="panel">
      <h2>LLM Runtime Status</h2>
      <p><strong>Semantic LLM called:</strong> <span class="badge ${semanticBadge}">${llm.semanticCalled ? "YES" : "NO"}</span></p>
      <p><strong>Semantic mode:</strong> ${escapeHtml(llm.semanticMode)}</p>
      <p><strong>Semantic suggestions:</strong> ${llm.semanticSuggestions}</p>
      <p><strong>Calc translation LLM:</strong> <span class="badge ${calcBadge}">calls=${llm.calcCalls}, success=${llm.calcSuccess}</span></p>
    </section>
  `;
}

function renderHtml(spec: AbstractSpec, proof: ProofReport): string {
  const totalPages = spec.dashboard_spec.pages.length;
  const totalVisuals = spec.dashboard_spec.pages.reduce((acc, page) => acc + page.visuals.length, 0);
  const totalMeasures = spec.semantic_model.measures.length;
  const totalDimensions = spec.semantic_model.dimensions.length;

  return `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Abstract Visualization - Demo</title>
  <style>
    :root {
      --bg: #f3efe7;
      --surface: #fffaf3;
      --ink: #1e2a32;
      --muted: #5e6b73;
      --accent: #d35400;
      --accent-2: #1f6f8b;
      --line: #e9dccf;
    }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      background: radial-gradient(circle at 10% 10%, #fff6e8 0%, var(--bg) 35%, #efe8dd 100%);
      color: var(--ink);
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }
    h1 {
      margin: 0;
      letter-spacing: 0.3px;
      color: var(--accent-2);
    }
    .sub {
      color: var(--muted);
      margin-top: 8px;
      margin-bottom: 18px;
    }
    .kpis {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .kpi {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.04);
    }
    .kpi .label {
      font-size: 12px;
      text-transform: uppercase;
      color: var(--muted);
    }
    .kpi .value {
      font-size: 26px;
      font-weight: 700;
      color: var(--accent);
      margin-top: 6px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.1fr 1fr;
      gap: 16px;
    }
    @media (max-width: 900px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .bar-row {
      margin: 10px 0;
    }
    .bar-title {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 5px;
    }
    .bar-track {
      background: #f5eadf;
      border-radius: 999px;
      height: 10px;
      overflow: hidden;
    }
    .bar {
      height: 100%;
      background: linear-gradient(90deg, var(--accent), #ff8a33);
    }
    .page-section {
      border-top: 1px dashed var(--line);
      padding-top: 12px;
      margin-top: 12px;
    }
    .visual-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .visual-item {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: #fffcf8;
    }
    .visual-item h4 {
      margin: 0 0 8px;
      font-size: 14px;
      color: var(--accent-2);
    }
    .visual-item p {
      margin: 5px 0;
      font-size: 12px;
    }
    .schema-wrap {
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fffdf9;
      padding: 8px;
    }
    .schema-svg {
      width: 100%;
      min-width: 760px;
      height: auto;
      display: block;
    }
    .evidence-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
    }
    .pipeline-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }
    .pipeline-step-panel {
      margin-bottom: 0;
    }
    .pipeline-step-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }
    .pipeline-step-head h3 {
      margin: 0;
      color: var(--accent-2);
      font-size: 16px;
    }
    .pipeline-step-evidence {
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .pipeline-step-sample-title {
      margin: 0 0 6px;
      font-weight: 700;
      font-size: 13px;
    }
    .pipeline-step-panel pre {
      margin: 0;
      background: #f9efe1;
      border: 1px solid #eadac4;
      border-radius: 8px;
      padding: 10px;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .evidence-panel pre {
      margin: 0;
      background: #f9efe1;
      border: 1px solid #eadac4;
      border-radius: 8px;
      padding: 10px;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .table-preview-panel h3 {
      margin-top: 0;
      margin-bottom: 8px;
      color: var(--accent-2);
    }
    .table-wrap {
      overflow-x: auto;
    }
    .proof-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 12px;
      font-size: 13px;
    }
    .proof-table th,
    .proof-table td {
      text-align: left;
      border-bottom: 1px solid var(--line);
      padding: 8px;
      vertical-align: top;
    }
    .proof-table pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 11px;
      line-height: 1.4;
      background: #f9efe1;
      border: 1px solid #eadac4;
      border-radius: 6px;
      padding: 6px;
    }
    .proof-notes {
      margin: 8px 0 0;
      padding-left: 20px;
      color: var(--muted);
      font-size: 12px;
    }
    .badge {
      display: inline-block;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }
    .badge-pass {
      background: #d8f2df;
      color: #195f2d;
    }
    .badge-warn {
      background: #ffe7c9;
      color: #8a4b00;
    }
    .badge-info {
      background: #ddeeff;
      color: #1a4f7a;
    }
    code {
      background: #f9efe1;
      padding: 2px 6px;
      border-radius: 6px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Visualisation Abstraite</h1>
    <p class="sub">Spec ID: <code>${escapeHtml(spec.id)}</code> | Source: <code>${escapeHtml(spec.source_fingerprint.slice(0, 12))}...</code></p>

    <section class="kpis">
      <article class="kpi"><div class="label">Pages</div><div class="value">${totalPages}</div></article>
      <article class="kpi"><div class="label">Visuals</div><div class="value">${totalVisuals}</div></article>
      <article class="kpi"><div class="label">Measures</div><div class="value">${totalMeasures}</div></article>
      <article class="kpi"><div class="label">Dimensions</div><div class="value">${totalDimensions}</div></article>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>Distribution des visuels par page</h2>
        ${spec.dashboard_spec.pages
          .map((page) => {
            const ratio = totalVisuals > 0 ? Math.max(4, Math.round((page.visuals.length / totalVisuals) * 100)) : 0;
            return `
              <div class="bar-row">
                <div class="bar-title">${escapeHtml(page.name)} (${page.visuals.length})</div>
                <div class="bar-track"><div class="bar" style="width: ${ratio}%"></div></div>
              </div>
            `;
          })
          .join("\n")}
      </article>

      <article class="panel">
        <h2>Résumé sémantique</h2>
        <p><strong>Fact table:</strong> ${escapeHtml(spec.semantic_model.fact_table)}</p>
        <p><strong>Grain:</strong> ${escapeHtml(spec.semantic_model.grain)}</p>
        <p><strong>Glossary entries:</strong> ${spec.semantic_model.glossary.length}</p>
        <p><strong>Lineage tables:</strong> ${spec.data_lineage.tables.length}</p>
      </article>
    </section>

    <section class="panel">
      <h2>Pages et visuels</h2>
      ${renderVisualList(spec)}
    </section>

    <section class="panel">
      <h2>Schema Graph</h2>
      <div class="schema-wrap">
        ${renderSchemaGraph(spec)}
      </div>
    </section>

    <section class="panel">
      <h2>Preuve par couche (outputs partiels)</h2>
      <div class="evidence-grid">
        ${renderLayerEvidence(spec)}
      </div>
    </section>

    <section class="panel">
      <h2>Pipeline Step Status & Output Sample</h2>
      <div class="pipeline-grid">
        ${renderPipelineStepStatus(spec, proof)}
      </div>
    </section>

    ${renderLlmStatusPanel(spec)}

    <section class="panel">
      <h2>Datasource Tables Preview (head 5)</h2>
      ${renderDatasourceTablePreview(spec)}
    </section>

    ${renderProofReport(proof)}
  </div>
</body>
</html>`;
}

export async function generateSimpleVisualFromAbstractJson(workspaceRoot: string): Promise<string> {
  const outputDir = path.join(workspaceRoot, "output");
  const transformedSpecPath = path.join(outputDir, "abstract-spec.json");
  const fallbackSpecPath = path.join(outputDir, "abstract-visualization.json");
  const outputPath = path.join(outputDir, "abstract-visualization.html");

  let inputPath = fallbackSpecPath;
  try {
    await stat(transformedSpecPath);
    inputPath = transformedSpecPath;
  } catch {
    inputPath = fallbackSpecPath;
  }

  const raw = await readFile(inputPath, "utf8");
  const spec = JSON.parse(raw) as AbstractSpec;

  const extractionProof = await loadExtractionProof(outputDir);

  const proof: ProofReport = {
    generatedAt: new Date().toISOString(),
    layerStatuses: computeLayerStatuses(spec),
    artifacts: await collectArtifactStatuses(outputDir),
  };

  if (extractionProof !== undefined) {
    proof.extractionProof = extractionProof;
  }

  const html = renderHtml(spec, proof);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, html, "utf8");

  return outputPath;
}

async function main(): Promise<void> {
  const outputPath = await generateSimpleVisualFromAbstractJson(process.cwd());
  process.stdout.write(`Visual demo generated: ${outputPath}\n`);
}

const shouldRunAsCli = process.argv[1] !== undefined && path.resolve(process.argv[1]).endsWith("generate-simple-visual.js");
if (shouldRunAsCli) {
  main().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`Visual demo failed: ${message}\n`);
    process.exitCode = 1;
  });
}
