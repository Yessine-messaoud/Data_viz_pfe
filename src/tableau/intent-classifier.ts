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

interface OpenAiChatChoice {
  message?: {
    content?: string;
  };
}

interface OpenAiChatResponse {
  choices?: OpenAiChatChoice[];
}

export class OpenAiCompatibleClient implements LlmClient {
  private readonly options: {
    baseUrl: string;
    model: string;
    apiKey?: string;
  };

  public constructor(options: OpenAiCompatibleClientOptions = {}) {
    const resolved: {
      baseUrl: string;
      model: string;
      apiKey?: string;
    } = {
      baseUrl: options.baseUrl ?? process.env.GROQ_BASE_URL ?? "https://api.groq.com/openai/v1",
      model: options.model ?? process.env.GROQ_MODEL ?? "llama-3.1-8b-instant",
    };

    const envKey = process.env.GROQ_API_KEY?.trim();
    const apiKey = options.apiKey ?? (envKey !== undefined && envKey.length > 0 ? envKey : undefined);
    if (apiKey !== undefined && apiKey.length > 0) {
      resolved.apiKey = apiKey;
    }

    this.options = resolved;
  }

  public async complete(messages: ChatMessage[]): Promise<string> {
    const response = await fetch(`${this.options.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: this.options.apiKey ? `Bearer ${this.options.apiKey}` : "",
      },
      body: JSON.stringify({
        model: this.options.model,
        messages,
        temperature: 0,
        response_format: { type: "json_object" },
      }),
    });

    if (!response.ok) {
      throw new Error(`LLM request failed with status ${response.status}`);
    }

    const data = (await response.json()) as OpenAiChatResponse;
    return data.choices?.[0]?.message?.content ?? "{}";
  }
}

export function createGroqIntentClassifier(): LlmIntentClassifier {
  return new LlmIntentClassifier(new OpenAiCompatibleClient());
}

export class LlmIntentClassifier implements IntentClassifier {
  public constructor(private readonly client: LlmClient) {}

  public async classify(request: string): Promise<IntentClassification> {
    const messages: ChatMessage[] = [
      {
        role: "system",
        content:
          "You classify migration requests into JSON with keys: action, target, modifications, confidence. Target must be powerbi.",
      },
      {
        role: "user",
        content: request,
      },
    ];

    const raw = await this.client.complete(messages);
    const parsed = JSON.parse(raw) as Partial<IntentClassification>;

    return {
      action: parsed.action ?? "convert_dashboard",
      target: "powerbi",
      modifications: Array.isArray(parsed.modifications) ? parsed.modifications.map((item) => String(item)) : [],
      confidence: typeof parsed.confidence === "number" ? parsed.confidence : 0.5,
    };
  }
}
