export declare function createTablePreviewHTML(tables: Array<{
    name: string;
    source?: string;
    columns: Array<{
        name: string;
        type: string;
    }>;
    rows: Array<Record<string, string | number | boolean | null>>;
}>): string;
export declare function generateSimpleVisualFromAbstractJson(workspaceRoot: string): Promise<string>;
