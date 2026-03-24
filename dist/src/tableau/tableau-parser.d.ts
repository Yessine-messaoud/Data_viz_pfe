import type { ParsedWorkbook, TableauParser } from "./interfaces.js";
export declare class XmlTableauParser implements TableauParser {
    private readonly parser;
    private readonly federatedResolver;
    constructor();
    parseTwbXml(xml: string): ParsedWorkbook;
}
