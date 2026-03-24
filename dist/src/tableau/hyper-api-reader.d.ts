export interface HyperColumnProfile {
    name: string;
    type: string;
}
export interface HyperTableProfile {
    table_name: string;
    columns: HyperColumnProfile[];
    sample_data: Array<Record<string, string | number | boolean | null>>;
    source: "hyper";
}
export interface HyperApiReadResult {
    tables: HyperTableProfile[];
    logs: string[];
    warnings: string[];
}
export declare function readHyperTablesFromBytes(bytes: Uint8Array, sourcePath: string): HyperApiReadResult;
