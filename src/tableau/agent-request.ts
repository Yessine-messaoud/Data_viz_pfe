import type {
  AgentRequest,
  AgentRequestBuilder,
  AgentRequestConfig,
  IntentClassification,
  ParsedWorkbook,
} from "./interfaces.js";

export class DefaultAgentRequestBuilder implements AgentRequestBuilder {
  public build(
    parsedWorkbook: ParsedWorkbook,
    intent: IntentClassification,
    config: AgentRequestConfig,
  ): AgentRequest {
    return {
      parsedWorkbook,
      intent,
      config,
    };
  }
}
