function isUnknownTable(columnRef) {
    return columnRef.table.trim().toLowerCase() === "unknown_table";
}
function isRawFederatedToken(columnRef) {
    return /federated\.[^.]+\./i.test(columnRef.column);
}
export class AbstractSpecValidator {
    validate(spec) {
        const issues = [];
        for (const [pageIndex, page] of spec.dashboard_spec.pages.entries()) {
            for (const [visualIndex, visual] of page.visuals.entries()) {
                const axes = visual.data_binding.axes;
                const axisEntries = [];
                if (axes.x !== undefined) {
                    axisEntries.push({ key: "x", ref: axes.x });
                }
                if (axes.y !== undefined) {
                    axisEntries.push({ key: "y", ref: axes.y });
                }
                if (axes.color !== undefined) {
                    axisEntries.push({ key: "color", ref: axes.color });
                }
                if (axes.size !== undefined) {
                    axisEntries.push({ key: "size", ref: axes.size });
                }
                if (axes.tooltip !== undefined) {
                    axisEntries.push({ key: "tooltip", ref: axes.tooltip });
                }
                if (axisEntries.length === 0) {
                    issues.push({
                        code: "EMPTY_VISUAL_BINDING",
                        message: `Visual ${visual.id} has no axis binding (x/y/color/size/tooltip).`,
                        path: `dashboard_spec.pages[${pageIndex}].visuals[${visualIndex}].data_binding.axes`,
                    });
                }
                for (const axis of axisEntries) {
                    const path = `dashboard_spec.pages[${pageIndex}].visuals[${visualIndex}].data_binding.axes.${axis.key}`;
                    if (isUnknownTable(axis.ref)) {
                        issues.push({
                            code: "UNKNOWN_TABLE",
                            message: `Unknown table detected for ${axis.key} axis in visual ${visual.id}`,
                            path,
                        });
                    }
                    if (isRawFederatedToken(axis.ref)) {
                        issues.push({
                            code: "RAW_FEDERATED_TOKEN",
                            message: `Raw federated token detected for ${axis.key} axis in visual ${visual.id}`,
                            path,
                        });
                    }
                }
            }
        }
        for (const [usageIndex, usage] of spec.data_lineage.columns_used.entries()) {
            const path = `data_lineage.columns_used[${usageIndex}].column`;
            if (isUnknownTable(usage.column)) {
                issues.push({
                    code: "UNKNOWN_TABLE",
                    message: `Unknown table detected in lineage usage for visual ${usage.visual_id}`,
                    path,
                });
            }
            if (isRawFederatedToken(usage.column)) {
                issues.push({
                    code: "RAW_FEDERATED_TOKEN",
                    message: `Raw federated token detected in lineage usage for visual ${usage.visual_id}`,
                    path,
                });
            }
        }
        return {
            valid: issues.length === 0,
            issueCount: issues.length,
            issues,
        };
    }
}
