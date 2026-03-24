import test from "node:test";
import assert from "node:assert/strict";
import { AdapterRegistry } from "../../src/adapter/adapter-registry.js";
const fakeAdapter = {
    validate(_spec) {
        return { valid: true, errors: [], warnings: [] };
    },
    async build() {
        return { artifactPath: "artifact.pbix", artifactBytes: new Uint8Array(), metadata: {} };
    },
    async deploy() {
        return { success: true };
    },
    getCapabilities() {
        return { target: "powerbi", supportsDeploy: true, supportsValidation: true, artifactTypes: ["pbix"] };
    },
};
test("register et resolve un adapter", () => {
    const registry = new AdapterRegistry();
    registry.register("powerbi", fakeAdapter);
    const resolved = registry.resolve("powerbi");
    assert.equal(resolved.getCapabilities().target, "powerbi");
});
