import type { ParsedWorkbook } from "./interfaces.js";
type JsonRecord = Record<string, unknown>;
declare function normalizeTableName(value: string): string;
declare function inferTableFromField(fieldName: string, tableCandidates: string[]): string | undefined;
declare function decodeFederatedToken(token: string, tableCandidates: string[]): string;
export declare class FederatedDatasourceResolver {
    resolve(parsedWorkbook: ParsedWorkbook, workbook: JsonRecord): ParsedWorkbook;
}
export { decodeFederatedToken, inferTableFromField, normalizeTableName };
