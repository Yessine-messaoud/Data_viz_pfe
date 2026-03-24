const FEDERATED_TOKEN_PREFIX = /^federated\.([^.]+)\.(.+)$/i;
const FEDERATED_TOKEN_IN_EXPRESSION = /federated\.[a-z0-9]+\.[^+)\n\r]+/gi;
function asArray(value) {
    if (value === undefined) {
        return [];
    }
    return Array.isArray(value) ? value : [value];
}
function asRecord(value) {
    if (typeof value !== "object" || value === null) {
        return undefined;
    }
    return value;
}
function sanitize(value) {
    return value.replace(/\[/g, "").replace(/\]/g, "").trim();
}
function normalizeTableName(value) {
    return sanitize(value)
        .replace(/\s+/g, "_")
        .replace(/[()]/g, "")
        .toLowerCase();
}
function tableNameFromEntity(value) {
    const normalized = normalizeTableName(value).replace(/!data$/i, "");
    return `${normalized}_data`;
}
function collectNamedConnectionTables(workbook) {
    const map = new Map();
    const datasources = asArray(asRecord(workbook["datasources"])?.["datasource"])
        .map((item) => asRecord(item))
        .filter((item) => item !== undefined);
    for (const datasource of datasources) {
        const datasourceName = String(datasource["name"] ?? datasource["caption"] ?? "");
        if (!datasourceName.startsWith("federated.")) {
            continue;
        }
        const federatedId = datasourceName.replace("federated.", "");
        const tables = new Set();
        const namedConnections = asArray(asRecord(asRecord(datasource["connection"])?.["named-connections"])?.["named-connection"])
            .map((item) => asRecord(item))
            .filter((item) => item !== undefined);
        for (const namedConnection of namedConnections) {
            const direct = [namedConnection["name"], namedConnection["caption"], namedConnection["table"]]
                .filter((value) => value !== undefined)
                .map((value) => sanitize(String(value)));
            for (const name of direct) {
                if (name.length > 0 && !name.startsWith("federated.")) {
                    tables.add(tableNameFromEntity(name));
                }
            }
            const connectionNode = asRecord(namedConnection["connection"]);
            const relationItems = asArray(connectionNode?.["relation"])
                .map((item) => asRecord(item))
                .filter((item) => item !== undefined);
            for (const relation of relationItems) {
                const tableValue = relation["table"] ?? relation["name"];
                if (tableValue !== undefined) {
                    const table = sanitize(String(tableValue));
                    if (table.length > 0 && table !== "unknown_table") {
                        tables.add(tableNameFromEntity(table));
                    }
                }
            }
        }
        map.set(federatedId, tables);
    }
    return map;
}
function inferTableFromField(fieldName, tableCandidates) {
    const clean = sanitize(fieldName);
    const sourceEntityMatch = clean.match(/\(([^)]+)!data\)/i);
    if (sourceEntityMatch?.[1] !== undefined) {
        const resolved = tableNameFromEntity(sourceEntityMatch[1]);
        if (tableCandidates.includes(resolved)) {
            return resolved;
        }
    }
    const tableHints = [
        "customer",
        "product",
        "sales_order",
        "sales_territory",
        "reseller",
        "sales",
        "date",
    ];
    const normalizedField = normalizeTableName(clean);
    for (const hint of tableHints) {
        const candidate = `${hint}_data`;
        if (normalizedField.includes(hint) && tableCandidates.includes(candidate)) {
            return candidate;
        }
    }
    if (tableCandidates.length === 1) {
        return tableCandidates[0];
    }
    const preferred = tableCandidates.find((table) => table.includes("sales_data"));
    return preferred ?? tableCandidates[0];
}
function decodeFederatedToken(token, tableCandidates) {
    const clean = sanitize(token);
    const prefix = clean.match(FEDERATED_TOKEN_PREFIX);
    if (prefix === null) {
        if (!clean.includes("federated.")) {
            return clean;
        }
        return clean.replace(FEDERATED_TOKEN_IN_EXPRESSION, (chunk) => decodeFederatedToken(chunk.trim(), tableCandidates));
    }
    const payload = prefix[2] ?? "";
    const parts = payload.split(":");
    if (parts.length < 2) {
        return clean;
    }
    const aggregation = sanitize(parts[0] ?? "").toLowerCase();
    const field = sanitize(parts[1] ?? "");
    const table = inferTableFromField(field, tableCandidates) ?? "unknown_table";
    if (aggregation === "sum") {
        return `sum(${table}.${field})`;
    }
    return `${table}.${field}`;
}
function resolveDatasourceTables(datasource, namedConnectionTables) {
    const inferredFromColumns = datasource.columns
        .map((column) => sanitize(column.name))
        .filter((name) => name.endsWith("_data"))
        .map((name) => normalizeTableName(name));
    const inferredFromSourceEntity = datasource.columns
        .map((column) => sanitize(column.name))
        .map((name) => name.match(/\(([^)]+)!data\)/i)?.[1])
        .filter((name) => name !== undefined)
        .map((name) => tableNameFromEntity(name));
    const existing = datasource.tables
        .map((table) => normalizeTableName(table.name))
        .filter((table) => table.length > 0 && table !== "unknown_table");
    const merged = new Set([
        ...existing,
        ...inferredFromColumns,
        ...inferredFromSourceEntity,
        ...Array.from(namedConnectionTables.values()),
    ]);
    return merged.size > 0 ? Array.from(merged) : ["unknown_table"];
}
function resolveColumns(columns, tableCandidates) {
    return columns.map((column) => {
        if (column.table !== undefined && column.table !== "unknown_table") {
            return column;
        }
        const inferred = inferTableFromField(column.name, tableCandidates);
        if (inferred === undefined) {
            return column;
        }
        return {
            ...column,
            table: inferred,
        };
    });
}
export class FederatedDatasourceResolver {
    resolve(parsedWorkbook, workbook) {
        const namedConnectionMap = collectNamedConnectionTables(workbook);
        const resolvedDatasources = parsedWorkbook.datasources.map((datasource) => {
            const federatedId = datasource.id.startsWith("federated.")
                ? datasource.id.replace("federated.", "")
                : datasource.name.startsWith("federated.")
                    ? datasource.name.replace("federated.", "")
                    : "";
            const namedConnectionTables = federatedId.length > 0 ? namedConnectionMap.get(federatedId) ?? new Set() : new Set();
            const resolvedTableNames = resolveDatasourceTables(datasource, namedConnectionTables);
            const resolvedTables = resolvedTableNames.map((tableName) => ({ name: tableName }));
            const resolvedColumns = resolveColumns(datasource.columns, resolvedTableNames);
            return {
                ...datasource,
                tables: resolvedTables,
                columns: resolvedColumns,
            };
        });
        const allCandidates = Array.from(new Set(resolvedDatasources
            .flatMap((datasource) => datasource.tables.map((table) => table.name))
            .map((table) => normalizeTableName(table))));
        const resolveTokens = (tokens) => tokens
            .map((token) => decodeFederatedToken(token, allCandidates))
            .filter((token) => token.length > 0 && token !== "unknown_table.");
        return {
            ...parsedWorkbook,
            datasources: resolvedDatasources,
            worksheets: parsedWorkbook.worksheets.map((worksheet) => ({
                ...worksheet,
                rows: resolveTokens(worksheet.rows),
                cols: resolveTokens(worksheet.cols),
                filters: resolveTokens(worksheet.filters),
            })),
        };
    }
}
export { decodeFederatedToken, inferTableFromField, normalizeTableName };
