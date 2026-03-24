import test from "node:test";
import assert from "node:assert/strict";
import { GraphBackedLineageQueryService } from "../../src/lineage/lineage-query-service.js";
class FakeRepo {
    async resetGraph() { }
    async upsertGraph(_graph) { }
    async shortestPath(from, to) {
        return [from, "table:fact_sales", to];
    }
    async detectCycles() {
        return [];
    }
    async upstreamNodes(nodeId) {
        if (nodeId === "visual:v1") {
            return ["table:fact_sales", "table:dim_date"];
        }
        if (nodeId === "column:fact_sales.sales_amount") {
            return ["visual:v1"];
        }
        return [];
    }
}
const lineage = {
    tables: [],
    joins: [
        {
            id: "j1",
            left_table: "fact_sales",
            right_table: "dim_date",
            type: "inner",
            keys: [{ left: { table: "fact_sales", column: "date_key" }, right: { table: "dim_date", column: "date_key" } }],
        },
    ],
    columns_used: [],
    visual_column_map: {},
};
test("service lineage utilise le graphe pour multi-hops", async () => {
    const service = new GraphBackedLineageQueryService(lineage, new FakeRepo());
    const tables = await service.getTablesForVisual("v1");
    assert.deepEqual(tables, ["fact_sales", "dim_date"]);
    const visuals = await service.getVisualsForColumn({ table: "fact_sales", column: "sales_amount" });
    assert.deepEqual(visuals, ["v1"]);
    const path = await service.getPathBetweenColumns({ table: "fact_sales", column: "sales_amount" }, { table: "dim_date", column: "year" });
    assert.equal(path.length, 3);
});
