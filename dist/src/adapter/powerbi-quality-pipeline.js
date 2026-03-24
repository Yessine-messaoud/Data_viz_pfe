import AdmZip from "adm-zip";
const KNOWN_DAX_FUNCTIONS = new Set([
    "SUM",
    "AVERAGE",
    "MIN",
    "MAX",
    "COUNT",
    "COUNTROWS",
    "DISTINCTCOUNT",
    "CALCULATE",
    "FILTER",
    "DIVIDE",
    "IF",
    "SWITCH",
    "RELATED",
    "RELATEDTABLE",
    "ALL",
    "VALUES",
    "DATEADD",
    "TOTALYTD",
]);
function normalizeTableName(value) {
    return value.trim().toLowerCase();
}
function normalizeColumnName(value) {
    return value.trim().toLowerCase();
}
function scoreFactCandidate(tableName, spec) {
    const profile = (spec.data_lineage.full_table_profiles ?? []).find((entry) => normalizeTableName(entry.table_name) === normalizeTableName(tableName));
    const columns = profile?.columns ?? [];
    const fk = columns.filter((column) => /(?:key|_key|keyid|_id|id|linekey)$/i.test(column.name)).length;
    const joinMany = spec.data_lineage.joins.filter((join) => normalizeTableName(join.left_table) === normalizeTableName(tableName)).length;
    const measure = columns.filter((column) => /(amount|qty|quantity|price|cost|sales|profit|revenue|margin)/i.test(column.name) &&
        /(integer|int|real|float|double|number|numeric|decimal)/i.test(column.type)).length;
    return {
        fk,
        joinMany,
        measure,
        total: fk * 3 + joinMany * 2 + measure,
    };
}
function inferFactTableFromSpec(spec) {
    const candidates = [...spec.data_lineage.tables, ...(spec.data_lineage.full_tables ?? [])];
    const unique = Array.from(new Set(candidates.map((table) => table.name)));
    if (unique.length === 0) {
        return undefined;
    }
    const ranked = unique
        .map((tableName) => ({ tableName, score: scoreFactCandidate(tableName, spec) }))
        .sort((left, right) => {
        if (right.score.total !== left.score.total) {
            return right.score.total - left.score.total;
        }
        if (right.score.fk !== left.score.fk) {
            return right.score.fk - left.score.fk;
        }
        if (right.score.measure !== left.score.measure) {
            return right.score.measure - left.score.measure;
        }
        return left.tableName.localeCompare(right.tableName);
    });
    return ranked[0]?.tableName;
}
function findAllFunctions(expression) {
    const regex = /\b([A-Z][A-Z0-9_]*)\(/g;
    const found = [];
    let match = regex.exec(expression);
    while (match !== null) {
        found.push(match[1] ?? "");
        match = regex.exec(expression);
    }
    return found;
}
function columnRefExists(columnRef, knownColumns, knownTables) {
    const tableKey = normalizeTableName(columnRef.table);
    if (!knownTables.has(tableKey)) {
        return false;
    }
    const fullKey = `${tableKey}.${normalizeColumnName(columnRef.column)}`;
    return knownColumns.has(fullKey);
}
function autoFixExpression(expression) {
    if (/\bSUMIF\s*\(/i.test(expression)) {
        const fixed = expression.replace(/\bSUMIF\s*\(/gi, "CALCULATE(SUM(");
        const closed = fixed.endsWith(")") ? `${fixed})` : `${fixed}))`;
        return {
            expression: closed,
            changed: true,
            reason: "SUMIF replaced by CALCULATE(SUM(...)) fallback.",
        };
    }
    if (/\[[^\]]+\]\.\[[^\]]+\]/.test(expression)) {
        const fixed = expression.replace(/\[([^\]]+)\]\.\[([^\]]+)\]/g, "$1[$2]");
        return {
            expression: fixed,
            changed: fixed !== expression,
            reason: "Converted SQL-like [Table].[Column] references to DAX Table[Column].",
        };
    }
    return { expression, changed: false };
}
function autoFixSpec(spec) {
    const warnings = [];
    const fixMeasure = (measure) => {
        const fixed = autoFixExpression(measure.expression);
        if (!fixed.changed) {
            return measure;
        }
        warnings.push({
            stage: "AutoFixer",
            code: "DAX_AUTOFIX",
            message: `Measure ${measure.name}: ${fixed.reason ?? "expression normalized"}`,
        });
        return {
            ...measure,
            expression: fixed.expression,
        };
    };
    const fixedSemanticMeasures = spec.semantic_model.measures.map(fixMeasure);
    const fixedManifestMeasures = spec.export_manifest.dax_measures.map((measure) => {
        const fixed = autoFixExpression(measure.expression);
        if (fixed.changed) {
            warnings.push({
                stage: "AutoFixer",
                code: "DAX_AUTOFIX",
                message: `Export measure ${measure.name}: ${fixed.reason ?? "expression normalized"}`,
            });
        }
        return {
            ...measure,
            expression: fixed.expression,
        };
    });
    const inferredFact = inferFactTableFromSpec(spec);
    const currentFact = spec.semantic_model.fact_table;
    const shouldFixFact = inferredFact !== undefined &&
        normalizeTableName(inferredFact) !== normalizeTableName(currentFact);
    if (shouldFixFact) {
        warnings.push({
            stage: "AutoFixer",
            code: "M_FACT_AUTOFIX",
            message: `fact_table corrected from ${currentFact} to ${inferredFact}.`,
        });
    }
    return {
        spec: {
            ...spec,
            semantic_model: {
                ...spec.semantic_model,
                ...(shouldFixFact && inferredFact !== undefined ? { fact_table: inferredFact } : {}),
                measures: fixedSemanticMeasures,
            },
            export_manifest: {
                ...spec.export_manifest,
                dax_measures: fixedManifestMeasures,
            },
        },
        warnings,
    };
}
function validateModel(spec) {
    const issues = [];
    const knownTables = new Set([...spec.data_lineage.tables, ...(spec.data_lineage.full_tables ?? [])].map((table) => normalizeTableName(table.name)));
    const knownColumns = new Set();
    for (const usage of spec.data_lineage.columns_used) {
        const table = normalizeTableName(usage.column.table);
        const column = normalizeColumnName(usage.column.column);
        knownColumns.add(`${table}.${column}`);
    }
    for (const profile of spec.data_lineage.full_table_profiles ?? []) {
        const table = normalizeTableName(profile.table_name);
        for (const column of profile.columns) {
            knownColumns.add(`${table}.${normalizeColumnName(column.name)}`);
        }
    }
    if (!knownTables.has(normalizeTableName(spec.semantic_model.fact_table))) {
        issues.push({
            stage: "ModelValidator",
            code: "UNKNOWN_FACT_TABLE",
            message: `Fact table ${spec.semantic_model.fact_table} is not present in data lineage tables.`,
        });
    }
    const inferredFact = inferFactTableFromSpec(spec);
    if (inferredFact === undefined) {
        issues.push({
            stage: "ModelValidator",
            code: "M_FACT",
            message: "Unable to infer fact table from lineage metadata.",
        });
    }
    else if (normalizeTableName(inferredFact) !== normalizeTableName(spec.semantic_model.fact_table)) {
        issues.push({
            stage: "ModelValidator",
            code: "M_FACT",
            message: `Fact table mismatch: semantic=${spec.semantic_model.fact_table}, inferred=${inferredFact}.`,
        });
    }
    for (const relationship of spec.semantic_model.relationships) {
        if (!columnRefExists(relationship.from, knownColumns, knownTables)) {
            issues.push({
                stage: "ModelValidator",
                code: "UNKNOWN_RELATIONSHIP_COLUMN",
                message: `Relationship source column ${relationship.from.table}.${relationship.from.column} does not exist.`,
            });
        }
        if (!columnRefExists(relationship.to, knownColumns, knownTables)) {
            issues.push({
                stage: "ModelValidator",
                code: "UNKNOWN_RELATIONSHIP_COLUMN",
                message: `Relationship target column ${relationship.to.table}.${relationship.to.column} does not exist.`,
            });
        }
    }
    return issues;
}
function validateDax(spec) {
    const issues = [];
    const knownColumnTokens = new Set();
    for (const usage of spec.data_lineage.columns_used) {
        knownColumnTokens.add(normalizeColumnName(usage.column.column).replace(/[^a-z0-9_]/g, ""));
    }
    for (const field of [...spec.semantic_model.entities, ...spec.semantic_model.dimensions]) {
        if (field.source !== undefined) {
            knownColumnTokens.add(normalizeColumnName(field.source.column).replace(/[^a-z0-9_]/g, ""));
        }
    }
    for (const measure of spec.export_manifest.dax_measures) {
        const functions = findAllFunctions(measure.expression.toUpperCase());
        for (const fn of functions) {
            const functionToken = normalizeColumnName(fn).replace(/[^a-z0-9_]/g, "");
            if (knownColumnTokens.has(functionToken)) {
                continue;
            }
            if (!KNOWN_DAX_FUNCTIONS.has(fn)) {
                issues.push({
                    stage: "DAXValidator",
                    code: "UNKNOWN_DAX_FUNCTION",
                    message: `Measure ${measure.name} uses unknown DAX function ${fn}.`,
                });
            }
        }
    }
    return issues;
}
function validatePbixBytes(pbixBytes) {
    const issues = [];
    const zip = new AdmZip(Buffer.from(pbixBytes));
    const names = new Set(zip.getEntries().map((entry) => entry.entryName));
    const requiredEntries = [
        "[Content_Types].xml",
        "DataModel/model.json",
        "Report/layout.json",
        "theme.json",
        "connections.json",
    ];
    for (const entry of requiredEntries) {
        if (!names.has(entry)) {
            issues.push({
                stage: "PBIXValidator",
                code: "MISSING_PBIX_ENTRY",
                message: `Missing required PBIX entry: ${entry}`,
            });
        }
    }
    return issues;
}
export class PBIXTemplate {
    createBaseArchive(spec) {
        const zip = new AdmZip();
        const contentTypes = `<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/DataModel/model.json" ContentType="application/json"/>
  <Override PartName="/Report/layout.json" ContentType="application/json"/>
</Types>`;
        zip.addFile("[Content_Types].xml", Buffer.from(contentTypes, "utf8"));
        zip.addFile("Metadata/version.json", Buffer.from(JSON.stringify({ version: spec.version }, null, 2), "utf8"));
        return zip;
    }
}
export class PowerBIQualityPipeline {
    prepareSpec(spec) {
        const fixed = autoFixSpec(spec);
        const modelIssues = validateModel(fixed.spec);
        const daxIssues = validateDax(fixed.spec);
        const issues = [...modelIssues, ...daxIssues];
        return {
            valid: issues.length === 0,
            fixedSpec: fixed.spec,
            issues,
            warnings: fixed.warnings,
        };
    }
    validatePbix(pbixBytes) {
        return validatePbixBytes(pbixBytes);
    }
}
