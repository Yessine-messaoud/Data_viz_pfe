import { createHash } from "node:crypto";
function toCanonicalJson(value) {
    if (value === null || typeof value !== "object") {
        return JSON.stringify(value);
    }
    if (Array.isArray(value)) {
        const items = value.map((item) => toCanonicalJson(item));
        return `[${items.join(",")}]`;
    }
    const obj = value;
    const keys = Object.keys(obj).sort();
    const entries = keys.map((key) => `${JSON.stringify(key)}:${toCanonicalJson(obj[key])}`);
    return `{${entries.join(",")}}`;
}
function bytesToHex(bytes) {
    return Buffer.from(bytes).toString("hex");
}
function hashSha256(data) {
    return createHash("sha256").update(data).digest("hex");
}
function toUuidFromSha256(sha256Hex) {
    const raw = Buffer.from(sha256Hex.slice(0, 32), "hex");
    if (raw.length < 16) {
        throw new Error("Invalid SHA-256 input for deterministic UUID generation");
    }
    // RFC4122 variant + v5 layout to keep a deterministic UUID-like identifier.
    const byte6 = raw[6] ?? 0;
    const byte8 = raw[8] ?? 0;
    raw[6] = (byte6 & 0x0f) | 0x50;
    raw[8] = (byte8 & 0x3f) | 0x80;
    const hex = bytesToHex(raw);
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
}
export class AbstractSpecBuilder {
    build(workbook, intent, semantic_model, lineage) {
        const source_fingerprint = hashSha256(workbook.raw);
        // ID must remain stable for same semantic inputs.
        const deterministicSeed = toCanonicalJson({
            source_fingerprint,
            intent,
            semantic_model,
            lineage,
        });
        const id = toUuidFromSha256(hashSha256(deterministicSeed));
        const log = [
            {
                level: "info",
                message: "AbstractSpec built from workbook + semantic artifacts",
                timestamp: new Date().toISOString(),
            },
        ];
        return {
            id,
            version: "0.1.0",
            source_fingerprint,
            dashboard_spec: {
                pages: [],
                global_filters: [],
                theme: {
                    name: "default",
                    palette: ["#0b3c5d", "#328cc1", "#d9b310", "#1d2731"],
                },
                refresh_policy: {
                    mode: "manual",
                },
            },
            semantic_model,
            data_lineage: lineage,
            export_manifest: {
                target: intent.target,
                model_config: {
                    dataset_name: workbook.source_name ?? "converted-dashboard",
                },
                dax_measures: [],
                m_queries: [],
                post_export_hooks: [],
            },
            build_log: log,
            warnings: [],
        };
    }
}
export { toCanonicalJson, hashSha256, toUuidFromSha256 };
