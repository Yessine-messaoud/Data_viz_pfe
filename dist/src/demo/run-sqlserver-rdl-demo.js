import { readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { writePaginatedRdlSqlServer } from "../adapter/paginated-report-builder.js";
import { VizAgentCore } from "../core/viz-agent-core.js";
const execFileAsync = promisify(execFile);
function isWorkbookFile(fileName) {
    const lower = fileName.toLowerCase();
    return lower.endsWith(".twb") || lower.endsWith(".twbx");
}
async function resolveInputFolder(workspaceRoot) {
    const candidates = [path.join(workspaceRoot, "input"), path.join(workspaceRoot, "Input")];
    for (const candidate of candidates) {
        try {
            const entries = await readdir(candidate);
            if (entries.length >= 0) {
                return candidate;
            }
        }
        catch {
            // Continue scanning fallback path.
        }
    }
    throw new Error("No input folder found. Create input/ or Input/ with a .twb or .twbx file.");
}
async function pickWorkbookFile(inputDir, preferredToken) {
    const entries = await readdir(inputDir, { withFileTypes: true });
    const files = entries.filter((entry) => entry.isFile() && isWorkbookFile(entry.name));
    const preferred = files.find((entry) => entry.name.toLowerCase().includes(preferredToken.toLowerCase()));
    const workbook = preferred ?? files[0];
    if (workbook === undefined) {
        throw new Error(`No .twb or .twbx file found in ${inputDir}`);
    }
    return path.join(inputDir, workbook.name);
}
async function testSqlConnection(server, database, integratedSecurity) {
    const args = ["-S", server, "-d", database, "-Q", "SELECT TOP 1 1 AS ok"];
    if (integratedSecurity) {
        args.splice(2, 0, "-E");
    }
    await execFileAsync("sqlcmd", args, { windowsHide: true });
}
function keepSingleChart(spec, preferredWorksheetName) {
    const allVisuals = spec.dashboard_spec.pages.flatMap((page) => page.visuals);
    if (allVisuals.length === 0) {
        throw new Error("No visuals found in source workbook to build single-chart RDL.");
    }
    const preferred = preferredWorksheetName?.trim().toLowerCase();
    const selectedVisual = (preferred !== undefined && preferred.length > 0
        ? allVisuals.find((visual) => visual.source_worksheet.trim().toLowerCase() === preferred)
        : undefined) ??
        (preferred !== undefined && preferred.length > 0
            ? allVisuals.find((visual) => visual.source_worksheet.trim().toLowerCase().includes(preferred))
            : undefined) ??
        allVisuals[0];
    if (selectedVisual === undefined) {
        throw new Error("Unable to select a source chart.");
    }
    const filteredPages = spec.dashboard_spec.pages
        .map((page) => ({
        ...page,
        visuals: page.visuals.filter((visual) => visual.id === selectedVisual.id),
    }))
        .filter((page) => page.visuals.length > 0);
    return {
        spec: {
            ...spec,
            dashboard_spec: {
                ...spec.dashboard_spec,
                pages: filteredPages,
            },
            data_lineage: {
                ...spec.data_lineage,
                columns_used: spec.data_lineage.columns_used.filter((usage) => usage.visual_id === selectedVisual.id),
                visual_column_map: {
                    [selectedVisual.id]: spec.data_lineage.visual_column_map[selectedVisual.id] ?? {
                        columns: [],
                        joins_used: [],
                        filters: [],
                    },
                },
            },
        },
        selectedWorksheet: selectedVisual.source_worksheet,
    };
}
export async function runSqlServerRdlDemo(workspaceRoot) {
    const sqlServer = process.env.SQL_SERVER ?? "localhost\\sqlexpress";
    const sqlDatabase = process.env.SQL_DATABASE ?? "AdventureWorksDW2022";
    const integratedSecurity = (process.env.SQL_INTEGRATED_SECURITY ?? "true").toLowerCase() !== "false";
    const preferredToken = process.env.INPUT_TOKEN ?? "vente";
    const preferredWorksheet = process.env.CHART_NAME ?? "Ventes par pays";
    await testSqlConnection(sqlServer, sqlDatabase, integratedSecurity);
    const inputDir = await resolveInputFolder(workspaceRoot);
    const workbookPath = await pickWorkbookFile(inputDir, preferredToken);
    const core = new VizAgentCore();
    const runResult = await core.run(workbookPath, workspaceRoot);
    const singleChart = keepSingleChart(runResult.spec, preferredWorksheet);
    const salesByCountryQuery = [
        "SELECT TOP 200",
        "  st.SalesTerritoryCountry AS Country,",
        "  SUM(fis.SalesAmount) AS TotalSales,",
        "  COUNT(*) AS NumberOfSales",
        "FROM dbo.FactInternetSales fis",
        "INNER JOIN dbo.DimSalesTerritory st ON fis.SalesTerritoryKey = st.SalesTerritoryKey",
        "GROUP BY st.SalesTerritoryCountry",
        "ORDER BY TotalSales DESC",
    ].join("\n");
    const rdlPath = await writePaginatedRdlSqlServer(singleChart.spec, path.join(workspaceRoot, "output"), {
        server: sqlServer,
        database: sqlDatabase,
        integratedSecurity,
        datasetName: "VenteParPays",
        query: salesByCountryQuery,
        fields: [
            { fieldName: "Country", sourceColumn: "Country" },
            { fieldName: "TotalSales", sourceColumn: "TotalSales" },
            { fieldName: "NumberOfSales", sourceColumn: "NumberOfSales" },
        ],
    });
    return {
        workbookPath,
        pbixPath: runResult.artifact,
        rdlPath,
        sqlServer,
        sqlDatabase,
        selectedWorksheet: singleChart.selectedWorksheet,
    };
}
async function main() {
    const result = await runSqlServerRdlDemo(process.cwd());
    process.stdout.write("SQL Server RDL demo generated:\n");
    process.stdout.write(`- Workbook: ${result.workbookPath}\n`);
    process.stdout.write(`- SQL Server: ${result.sqlServer}\n`);
    process.stdout.write(`- SQL Database: ${result.sqlDatabase}\n`);
    process.stdout.write(`- Selected chart: ${result.selectedWorksheet}\n`);
    process.stdout.write(`- PBIX artifact: ${result.pbixPath}\n`);
    process.stdout.write(`- SQL Server RDL: ${result.rdlPath}\n`);
}
const currentFile = fileURLToPath(import.meta.url);
const entryFile = process.argv[1];
if (entryFile !== undefined && path.resolve(entryFile) === path.resolve(currentFile)) {
    main().catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        process.stderr.write(`SQL Server RDL demo failed: ${message}\n`);
        process.exitCode = 1;
    });
}
