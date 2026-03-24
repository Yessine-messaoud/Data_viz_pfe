import type { AgentRequest, AgentRequestBuilder, AgentRequestConfig, IntentClassification, ParsedWorkbook } from "./interfaces.js";
export declare class DefaultAgentRequestBuilder implements AgentRequestBuilder {
    build(parsedWorkbook: ParsedWorkbook, intent: IntentClassification, config: AgentRequestConfig): AgentRequest;
}
