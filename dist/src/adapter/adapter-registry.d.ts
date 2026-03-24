import type { ITargetAdapter } from "./interfaces.js";
export declare class AdapterRegistry {
    private readonly adapters;
    register(target: string, adapter: ITargetAdapter): void;
    resolve(target: string): ITargetAdapter;
}
