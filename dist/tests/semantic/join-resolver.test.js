import test from "node:test";
import assert from "node:assert/strict";
import { TableauJoinResolver } from "../../src/semantic/join-resolver.js";
test("resout les joins parses vers JoinDef", () => {
    const resolver = new TableauJoinResolver();
    const joins = resolver.resolve([
        {
            id: "j1",
            leftTable: "fact_sales",
            rightTable: "dim_date",
            joinType: "inner",
            keys: [{ leftColumn: "date_key", rightColumn: "date_key" }],
        },
    ]);
    assert.equal(joins[0]?.left_table, "fact_sales");
    assert.equal(joins[0]?.keys.length, 1);
});
