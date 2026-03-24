function clampConfidence(value, fallback) {
    const numeric = typeof value === "number" ? value : Number.NaN;
    if (!Number.isFinite(numeric)) {
        return fallback;
    }
    if (numeric < 0) {
        return 0;
    }
    if (numeric > 1) {
        return 1;
    }
    return numeric;
}
function sanitizeSuggestedExpression(expression) {
    const normalized = expression
        .replace(/\bcountd\s*\(/gi, "DISTINCTCOUNT(")
        .replace(/\bavg\s*\(/gi, "AVERAGE(");
    if (/\b(fixed|window|running|table)\b/i.test(normalized)) {
        return "0";
    }
    return normalized;
}
function toColumnLabel(column) {
    return `${column.table}.${column.column}`;
}
function extractJsonObject(text) {
    const trimmed = text.trim();
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
        return trimmed;
    }
    const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
    if (fenced?.[1] !== undefined) {
        const candidate = fenced[1].trim();
        if (candidate.startsWith("{") && candidate.endsWith("}")) {
            return candidate;
        }
    }
    const first = trimmed.indexOf("{");
    const last = trimmed.lastIndexOf("}");
    if (first >= 0 && last > first) {
        return trimmed.slice(first, last + 1);
    }
    return undefined;
}
function buildDeterministicResult(base, context) {
    const renamedDimensions = base.dimensions
        .filter((dimension) => context.glossary[dimension.name] !== undefined)
        .map((dimension) => ({
        from: dimension.name,
        to: context.glossary[dimension.name] ?? dimension.name,
        confidence: 0.92,
    }));
    const suggestedMeasures = context.complexCalcs.map((calc, index) => ({
        name: `Suggested Measure ${index + 1}`,
        expression: sanitizeSuggestedExpression(calc),
        confidence: 0.72,
    }));
    return {
        renamedDimensions,
        suggestedMeasures,
        disambiguationNotes: context.ambiguousColumns.map((column) => `Ambiguity detected for ${toColumnLabel(column)}.`),
    };
}
export class HybridSemanticEnricher {
    options;
    constructor(options = {}) {
        const resolved = {
            model: options.model ?? process.env.MISTRAL_MODEL ?? "mistral-small-latest",
            baseUrl: options.baseUrl ?? process.env.MISTRAL_BASE_URL ?? "https://api.mistral.ai/v1",
            provider: options.provider ?? "mistral",
        };
        if (options.apiKey !== undefined) {
            resolved.apiKey = options.apiKey;
        }
        if (options.fetchImpl !== undefined) {
            resolved.fetchImpl = options.fetchImpl;
        }
        this.options = resolved;
    }
    getFetch() {
        return this.options.fetchImpl ?? fetch;
    }
    getApiKey() {
        const direct = this.options.apiKey?.trim();
        if ((direct?.length ?? 0) > 0) {
            return direct;
        }
        const env = process.env.MISTRAL_API_KEY?.trim();
        if ((env?.length ?? 0) > 0) {
            return env;
        }
        const legacyEnv = process.env.GROQ_API_KEY?.trim();
        if ((legacyEnv?.length ?? 0) > 0) {
            return legacyEnv;
        }
        return undefined;
    }
    getLocalLlamaEndpoint() {
        return process.env.LOCAL_LLM_BASE_URL?.trim() || "http://127.0.0.1:11434";
    }
    getLocalLlamaModel() {
        return process.env.LOCAL_LLM_MODEL?.trim() || "llama3";
    }
    buildCloudMessages(base, context) {
        const payload = {
            dimensions: base.dimensions.map((dimension) => dimension.name),
            glossary: context.glossary,
            ambiguousColumns: context.ambiguousColumns.map((column) => toColumnLabel(column)),
            complexCalcs: context.complexCalcs,
        };
        return [
            {
                role: "system",
                content: "You are a semantic BI model assistant. Return only valid JSON with keys: renamedDimensions, suggestedMeasures, disambiguationNotes.",
            },
            {
                role: "user",
                content: "Using this semantic context, propose conservative semantic enrichments. JSON schema: {\"renamedDimensions\":[{\"from\":string,\"to\":string,\"confidence\":number}],\"suggestedMeasures\":[{\"name\":string,\"expression\":string,\"confidence\":number}],\"disambiguationNotes\":[string]}. Input:\n" +
                    JSON.stringify(payload),
            },
        ];
    }
    parseCloudResult(content) {
        const jsonText = extractJsonObject(content);
        if (jsonText === undefined) {
            throw new Error("Unable to parse JSON payload from cloud LLM response.");
        }
        const parsed = JSON.parse(jsonText);
        const renamedDimensions = (parsed.renamedDimensions ?? [])
            .filter((item) => typeof item.from === "string" && typeof item.to === "string")
            .map((item) => ({
            from: item.from,
            to: item.to,
            confidence: clampConfidence(item.confidence, 0.7),
        }));
        const suggestedMeasures = (parsed.suggestedMeasures ?? [])
            .filter((item) => typeof item.name === "string" && typeof item.expression === "string")
            .map((item) => ({
            name: item.name,
            expression: sanitizeSuggestedExpression(item.expression),
            confidence: clampConfidence(item.confidence, 0.7),
        }));
        const disambiguationNotes = (parsed.disambiguationNotes ?? []).filter((item) => typeof item === "string" && item.trim().length > 0);
        return {
            renamedDimensions,
            suggestedMeasures,
            disambiguationNotes,
        };
    }
    async enrichWithMistral(base, context) {
        const apiKey = this.getApiKey();
        if (apiKey === undefined || this.options.provider === "none") {
            throw new Error("Mistral API key is not configured.");
        }
        const response = await this.getFetch()(`${this.options.baseUrl}/chat/completions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${apiKey}`,
            },
            body: JSON.stringify({
                model: this.options.model,
                temperature: 0.2,
                messages: this.buildCloudMessages(base, context),
            }),
        });
        if (!response.ok) {
            throw new Error(`Mistral request failed with status ${response.status}`);
        }
        const data = (await response.json());
        const content = data.choices?.[0]?.message?.content;
        if (content === undefined || content.trim().length === 0) {
            throw new Error("Mistral returned an empty response.");
        }
        return this.parseCloudResult(content);
    }
    async enrichWithLocalLlama3(base, context) {
        const endpoint = `${this.getLocalLlamaEndpoint().replace(/\/$/, "")}/api/generate`;
        const prompt = "You are a semantic BI model assistant. Return only valid JSON with keys: renamedDimensions, suggestedMeasures, disambiguationNotes. " +
            JSON.stringify({
                dimensions: base.dimensions.map((dimension) => dimension.name),
                glossary: context.glossary,
                ambiguousColumns: context.ambiguousColumns.map((column) => toColumnLabel(column)),
                complexCalcs: context.complexCalcs,
            });
        const response = await this.getFetch()(endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                model: this.getLocalLlamaModel(),
                prompt,
                format: "json",
                stream: false,
            }),
        });
        if (!response.ok) {
            throw new Error(`Local llama3 request failed with status ${response.status}`);
        }
        const payload = (await response.json());
        const content = payload.response;
        if (content === undefined || content.trim().length === 0) {
            throw new Error("Local llama3 returned an empty response.");
        }
        return this.parseCloudResult(content);
    }
    async enrich(base, context) {
        const deterministic = buildDeterministicResult(base, context);
        try {
            const llmResult = await this.enrichWithMistral(base, context);
            return {
                renamedDimensions: llmResult.renamedDimensions.length > 0 ? llmResult.renamedDimensions : deterministic.renamedDimensions,
                suggestedMeasures: llmResult.suggestedMeasures.length > 0 ? llmResult.suggestedMeasures : deterministic.suggestedMeasures,
                disambiguationNotes: [...deterministic.disambiguationNotes, ...llmResult.disambiguationNotes],
            };
        }
        catch (error) {
            const mistralMessage = error instanceof Error ? error.message : "unknown Mistral error";
            try {
                const localResult = await this.enrichWithLocalLlama3(base, context);
                return {
                    renamedDimensions: localResult.renamedDimensions.length > 0 ? localResult.renamedDimensions : deterministic.renamedDimensions,
                    suggestedMeasures: localResult.suggestedMeasures.length > 0 ? localResult.suggestedMeasures : deterministic.suggestedMeasures,
                    disambiguationNotes: [
                        ...deterministic.disambiguationNotes,
                        `LLM_FALLBACK: mistral_unavailable=${mistralMessage}`,
                        ...localResult.disambiguationNotes,
                    ],
                };
            }
            catch (localError) {
                const localMessage = localError instanceof Error ? localError.message : "unknown local llama3 error";
                return {
                    ...deterministic,
                    disambiguationNotes: [
                        ...deterministic.disambiguationNotes,
                        `LLM_FALLBACK: mistral=${mistralMessage}; local_llama3=${localMessage}`,
                    ],
                };
            }
        }
    }
}
