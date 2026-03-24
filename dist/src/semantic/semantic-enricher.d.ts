import type { SemanticEnricher, SemanticEnrichmentContext, SemanticEnrichmentResult } from "./interfaces.js";
import type { SemanticModel } from "../spec/abstract-spec.js";
export interface HybridSemanticEnricherOptions {
    apiKey?: string;
    model?: string;
    baseUrl?: string;
    provider?: "mistral" | "none";
    fetchImpl?: typeof fetch;
}
export declare class HybridSemanticEnricher implements SemanticEnricher {
    private readonly options;
    constructor(options?: HybridSemanticEnricherOptions);
    private getFetch;
    private getApiKey;
    private getLocalLlamaEndpoint;
    private getLocalLlamaModel;
    private buildCloudMessages;
    private parseCloudResult;
    private enrichWithMistral;
    private enrichWithLocalLlama3;
    enrich(base: SemanticModel, context: SemanticEnrichmentContext): Promise<SemanticEnrichmentResult>;
}
