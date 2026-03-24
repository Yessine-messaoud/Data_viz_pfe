const OP_PRIORITY = {
    "normalize-schema": 10,
    "rename-table": 20,
    "rename-column": 30,
    "add-filter": 40,
    "create-bridge-table": 50,
    "add-date-dimension": 60,
    custom: 100,
};
function inferType(modification) {
    const lower = modification.toLowerCase();
    if (lower.includes("rename") && lower.includes("table")) {
        return "rename-table";
    }
    if (lower.includes("rename") && lower.includes("column")) {
        return "rename-column";
    }
    if (lower.includes("filter")) {
        return "add-filter";
    }
    if (lower.includes("bridge") || lower.includes("m:n") || lower.includes("many-to-many")) {
        return "create-bridge-table";
    }
    if (lower.includes("date")) {
        return "add-date-dimension";
    }
    if (lower.includes("normalize") || lower.includes("star schema")) {
        return "normalize-schema";
    }
    return "custom";
}
export class IntentTransformPlanner {
    plan(modifications) {
        const baseOps = modifications.map((modification, index) => {
            const type = inferType(modification);
            return {
                id: `op_${index + 1}`,
                order: OP_PRIORITY[type],
                type,
                payload: { text: modification },
                source: "intent",
            };
        });
        const withSystemOps = [
            {
                id: "op_sys_normalize",
                order: OP_PRIORITY["normalize-schema"],
                type: "normalize-schema",
                payload: { reason: "baseline" },
                source: "system",
            },
            ...baseOps,
        ];
        return withSystemOps
            .sort((a, b) => a.order - b.order)
            .map((op, index) => ({
            ...op,
            order: index + 1,
        }));
    }
}
