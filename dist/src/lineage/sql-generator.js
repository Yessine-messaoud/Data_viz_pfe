function toSqlColumn(column) {
    return `[${column.table}].[${column.column}]`;
}
export function generateSQL(spec, visualId) {
    const visualLineage = spec.data_lineage.visual_column_map[visualId];
    if (visualLineage === undefined) {
        throw new Error(`Unknown visual id: ${visualId}`);
    }
    const columns = visualLineage.columns;
    const primaryTable = columns[0]?.table ?? spec.semantic_model.fact_table;
    const selectClause = columns.length > 0
        ? columns.map((column) => toSqlColumn(column)).join(", ")
        : "COUNT(1) AS [row_count]";
    const joinClauses = spec.data_lineage.joins
        .filter((join) => visualLineage.joins_used.length === 0 || visualLineage.joins_used.includes(join.id))
        .map((join) => {
        const key = join.keys[0];
        const onClause = key === undefined
            ? "1 = 1"
            : `[${join.left_table}].[${key.left.column}] = [${join.right_table}].[${key.right.column}]`;
        const joinType = join.type.toUpperCase();
        return `${joinType} JOIN [${join.right_table}] ON ${onClause}`;
    })
        .join("\n");
    const whereClause = visualLineage.filters
        .map((filter) => {
        const left = `[${filter.column.table}].[${filter.column.column}]`;
        if (Array.isArray(filter.value)) {
            const values = filter.value.map((value) => `'${String(value)}'`).join(", ");
            return `${left} IN (${values})`;
        }
        return `${left} = '${String(filter.value)}'`;
    })
        .join(" AND ");
    const lines = [`SELECT ${selectClause}`, `FROM [${primaryTable}]`];
    if (joinClauses.length > 0) {
        lines.push(joinClauses);
    }
    if (whereClause.length > 0) {
        lines.push(`WHERE ${whereClause}`);
    }
    return lines.join("\n");
}
