import test from "node:test";
import assert from "node:assert/strict";

import { XmlTableauParser } from "../../src/tableau/tableau-parser.js";

const twbXml = `<?xml version="1.0" encoding="utf-8"?>
<workbook>
  <worksheets>
    <worksheet name="SalesSheet">
      <table>
        <rows>[Sales]</rows>
        <cols>[Region]</cols>
        <filter>[Category]</filter>
      </table>
      <panes>
        <mark>bar</mark>
      </panes>
    </worksheet>
  </worksheets>
  <datasources>
    <datasource name="ds1" caption="MainDS">
      <connection>
        <relation name="fact_sales" table="fact_sales" schema="dbo" />
      </connection>
      <column name="[Sales]" caption="Sales" datatype="real" table="fact_sales" />
      <column name="[Calc]" caption="Calc" datatype="real">
        <calculation formula="SUM([Sales])" />
      </column>
      <column name="[p.Region]" caption="Region Param" datatype="string" param-domain-type="list" value="EU" />
    </datasource>
  </datasources>
  <dashboards>
    <dashboard name="Dashboard1">
      <zones>
        <zone name="z1" type="layout-basic" x="0" y="0" w="100" h="100" />
      </zones>
    </dashboard>
  </dashboards>
</workbook>`;

test("parse .twb xml vers ParsedWorkbook", () => {
  const parser = new XmlTableauParser();
  const parsed = parser.parseTwbXml(twbXml);

  assert.equal(parsed.worksheets.length, 1);
  assert.equal(parsed.datasources.length, 1);
  assert.equal(parsed.calculated_fields.length, 1);
  assert.equal(parsed.dashboards.length, 1);
  assert.equal(parsed.parameters.length, 1);
  assert.equal(parsed.worksheets[0]?.name, "SalesSheet");
  assert.equal(parsed.dashboards[0]?.zones[0]?.id, "z1");
  assert.equal(parsed.dashboards[0]?.zones[0]?.name, "z1");
});
