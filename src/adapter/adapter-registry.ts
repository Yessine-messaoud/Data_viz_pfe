import type { ITargetAdapter } from "./interfaces.js";

export class AdapterRegistry {
  private readonly adapters = new Map<string, ITargetAdapter>();

  public register(target: string, adapter: ITargetAdapter): void {
    this.adapters.set(target.toLowerCase(), adapter);
  }

  public resolve(target: string): ITargetAdapter {
    const adapter = this.adapters.get(target.toLowerCase());
    if (adapter === undefined) {
      throw new Error(`No adapter registered for target: ${target}`);
    }
    return adapter;
  }
}
