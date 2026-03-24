export class AdapterRegistry {
    adapters = new Map();
    register(target, adapter) {
        this.adapters.set(target.toLowerCase(), adapter);
    }
    resolve(target) {
        const adapter = this.adapters.get(target.toLowerCase());
        if (adapter === undefined) {
            throw new Error(`No adapter registered for target: ${target}`);
        }
        return adapter;
    }
}
