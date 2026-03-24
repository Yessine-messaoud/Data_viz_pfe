export class OpenAiCompatibleClient {
    options;
    constructor(options = {}) {
        const resolved = {
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
    async complete(messages) {
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
        const data = (await response.json());
        return data.choices?.[0]?.message?.content ?? "{}";
    }
}
export function createGroqIntentClassifier() {
    return new LlmIntentClassifier(new OpenAiCompatibleClient());
}
export class LlmIntentClassifier {
    client;
    constructor(client) {
        this.client = client;
    }
    async classify(request) {
        const messages = [
            {
                role: "system",
                content: "You classify migration requests into JSON with keys: action, target, modifications, confidence. Target must be powerbi.",
            },
            {
                role: "user",
                content: request,
            },
        ];
        const raw = await this.client.complete(messages);
        const parsed = JSON.parse(raw);
        return {
            action: parsed.action ?? "convert_dashboard",
            target: "powerbi",
            modifications: Array.isArray(parsed.modifications) ? parsed.modifications.map((item) => String(item)) : [],
            confidence: typeof parsed.confidence === "number" ? parsed.confidence : 0.5,
        };
    }
}
