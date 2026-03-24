import type { IntentClassification, IntentClassifier } from "./interfaces.js";
export interface ChatMessage {
    role: "system" | "user" | "assistant";
    content: string;
}
export interface LlmClient {
    complete(messages: ChatMessage[]): Promise<string>;
}
export interface OpenAiCompatibleClientOptions {
    baseUrl?: string;
    model?: string;
    apiKey?: string;
}
export declare class OpenAiCompatibleClient implements LlmClient {
    private readonly options;
    constructor(options?: OpenAiCompatibleClientOptions);
    complete(messages: ChatMessage[]): Promise<string>;
}
export declare function createGroqIntentClassifier(): LlmIntentClassifier;
export declare class LlmIntentClassifier implements IntentClassifier {
    private readonly client;
    constructor(client: LlmClient);
    classify(request: string): Promise<IntentClassification>;
}
