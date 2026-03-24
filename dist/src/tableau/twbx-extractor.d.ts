import type { TwbxExtractionResult, TwbxExtractor } from "./interfaces.js";
export declare class ZipTwbxExtractor implements TwbxExtractor {
    extract(buffer: Uint8Array): TwbxExtractionResult;
}
