import test from "node:test";
import assert from "node:assert/strict";
import { LlmIntentClassifier } from "../../src/tableau/intent-classifier.js";
class FakeClient {
    async complete(_messages) {
        return JSON.stringify({
            action: "convert",
            target: "powerbi",
            modifications: ["rename visuals", "add date table"],
            confidence: 0.88,
        });
    }
}
test("classifie intention en format strict", async () => {
    const classifier = new LlmIntentClassifier(new FakeClient());
    const intent = await classifier.classify("Convert this dashboard to Power BI");
    assert.equal(intent.target, "powerbi");
    assert.equal(intent.action, "convert");
    assert.equal(intent.modifications.length, 2);
    assert.equal(intent.confidence, 0.88);
});
