import test from "node:test";
import assert from "node:assert/strict";
import { DefaultSchemaMapper } from "../../src/semantic/schema-mapper.js";
test("mappe type et visuel Tableau vers cible", () => {
    const mapper = new DefaultSchemaMapper();
    assert.equal(mapper.mapTypes("integer"), "int64");
    assert.equal(mapper.mapTypes("float"), "double");
    assert.equal(mapper.mapVisualType("texttable"), "table");
});
