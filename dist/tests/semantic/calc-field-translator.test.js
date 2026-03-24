import test from "node:test";
import assert from "node:assert/strict";
import { TableauCalcFieldTranslator } from "../../src/semantic/calc-field-translator.js";
import { buildGroqCalcMessages, validateDaxExpressionForRetry, } from "../../src/demo/parsed-workbook-to-abstract.js";
test("traduction deterministe SUM", () => {
    const translator = new TableauCalcFieldTranslator();
    const result = translator.translateTableauFormula("SUM([Sales])");
    assert.equal(result.daxExpression, "SUM([Sales])");
    assert.equal(result.usedLlm, false);
});
test("LOD bascule sur branche LLM", () => {
    const translator = new TableauCalcFieldTranslator();
    const result = translator.translateTableauFormula("{ FIXED [Region]: SUM([Sales]) }");
    assert.equal(result.usedLlm, true);
});
test("COUNTD est traduit en DISTINCTCOUNT", () => {
    const translator = new TableauCalcFieldTranslator();
    const result = translator.translateTableauFormula("COUNTD([Order ID])");
    assert.equal(result.daxExpression, "DISTINCTCOUNT([Order ID])");
    assert.equal(result.usedLlm, false);
});
test("FIX3 prompt LLM inclut schema complet, mesures existantes et few-shot", () => {
    const workbook = {
        worksheets: [],
        datasources: [
            {
                id: "ds",
                name: "SalesDS",
                tables: [{ name: "sales_data" }],
                columns: [
                    { id: "[Sales Amount]", name: "[Sales Amount]", dataType: "double", table: "sales_data" },
                    { id: "[Tax Amt]", name: "[Tax Amt]", dataType: "double", table: "sales_data" },
                ],
            },
        ],
        calculated_fields: [],
        dashboards: [],
        parameters: [],
    };
    const context = {
        formula: "SUM([Sales Amount]) + SUM([Tax Amt])",
        parsedWorkbook: workbook,
        existingMeasures: ["Sum Total Sales=SUM(sales_data[Sales Amount])"],
    };
    const messages = buildGroqCalcMessages(context);
    const payload = JSON.parse(messages[1]?.content ?? "{}");
    assert.equal(payload.availableTablesAndColumns?.sales_data?.includes("Sales Amount"), true);
    assert.equal(payload.existingMeasures?.length, 1);
    assert.equal((payload.fewShot?.length ?? 0) >= 3, true);
});
test("FIX3 validation DAX reject dot notation and accept Table[Column]", () => {
    const invalid = validateDaxExpressionForRetry("SUM(sales_data.SalesAmount)");
    const valid = validateDaxExpressionForRetry("SUM(sales_data[SalesAmount])");
    assert.equal(invalid.valid, false);
    assert.equal(valid.valid, true);
});
