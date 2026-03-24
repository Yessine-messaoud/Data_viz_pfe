import test from "node:test";
import assert from "node:assert/strict";

import { IntentTransformPlanner } from "../../src/transform/transform-planner.js";

test("planifie les operations dans un ordre stable", () => {
  const planner = new IntentTransformPlanner();
  const ops = planner.plan(["rename column customer_id", "add date table", "add filter region = EU"]);

  assert.equal(ops[0]?.type, "normalize-schema");
  assert.equal(ops.some((op) => op.type === "rename-column"), true);
  assert.equal(ops.some((op) => op.type === "add-date-dimension"), true);
});
