function looksLikeDateColumn(columnName) {
    const lower = columnName.toLowerCase();
    return lower.includes("date") || lower.includes("month") || lower.includes("year") || lower.includes("quarter");
}
export class SemanticStarSchemaBuilder {
    build(model, lineage) {
        const factTable = model.fact_table;
        const dimensionMap = new Map();
        for (const dimension of model.dimensions) {
            const source = dimension.source;
            if (source === undefined) {
                continue;
            }
            const tableName = source.table;
            const columnName = source.column;
            if (columnName === undefined || tableName === factTable) {
                continue;
            }
            const existing = dimensionMap.get(tableName);
            if (existing === undefined) {
                dimensionMap.set(tableName, {
                    name: tableName,
                    keyColumn: `${tableName}_key`,
                    sourceColumns: [source],
                });
            }
            else {
                existing.sourceColumns.push(source);
            }
        }
        const dimensions = Array.from(dimensionMap.values());
        const hasManyToMany = model.relationships.some((relationship) => relationship.cardinality === "many-to-many");
        const bridges = [];
        if (hasManyToMany && dimensions.length >= 2) {
            bridges.push({
                name: `${dimensions[0]?.name ?? "left"}_${dimensions[1]?.name ?? "right"}_bridge`,
                leftDimension: dimensions[0]?.name ?? "left",
                rightDimension: dimensions[1]?.name ?? "right",
            });
        }
        const hasDateInDimensions = dimensions.some((dimension) => dimension.sourceColumns.some((sourceColumn) => looksLikeDateColumn(sourceColumn.column)));
        if (!hasDateInDimensions) {
            const hasDateInLineage = lineage.columns_used.some((usage) => looksLikeDateColumn(usage.column.column));
            if (hasDateInLineage) {
                dimensions.push({
                    name: "date_dimension",
                    keyColumn: "date_key",
                    sourceColumns: [{ table: "date_dimension", column: "Date" }],
                });
            }
        }
        return {
            factTable,
            dimensions,
            bridges,
            hasAutoDateDimension: dimensions.some((dimension) => dimension.name === "date_dimension"),
        };
    }
}
