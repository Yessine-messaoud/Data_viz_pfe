import test from "node:test";
import assert from "node:assert/strict";

import { LlmIntentClassifier } from "../../src/tableau/intent-classifier.js";
import type { ChatMessage, LlmClient } from "../../src/tableau/intent-classifier.js";

class FakeClient implements LlmClient {
  public async complete(_messages: ChatMessage[]): Promise<string> {
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
