import test from "node:test";
import assert from "node:assert/strict";

import { DefaultAgentRequestBuilder } from "../../src/tableau/agent-request.js";
import type { IntentClassification, ParsedWorkbook } from "../../src/tableau/interfaces.js";

const parsedWorkbook: ParsedWorkbook = {
  worksheets: [],
  datasources: [],
  calculated_fields: [],
  dashboards: [],
  parameters: [],
};

const intent: IntentClassification = {
  action: "convert",
  target: "powerbi",
  modifications: ["keep filters"],
  confidence: 0.9,
};

test("compose AgentRequest depuis workbook + intent + config", () => {
  const builder = new DefaultAgentRequestBuilder();
  const request = builder.build(parsedWorkbook, intent, {
    environment: "dev",
    strictMode: true,
  });

  assert.equal(request.intent.target, "powerbi");
  assert.equal(request.config.strictMode, true);
});
