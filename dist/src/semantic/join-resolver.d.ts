import type { JoinDef } from "../spec/abstract-spec.js";
import type { JoinResolver, ParsedJoinInput } from "./interfaces.js";
export declare class TableauJoinResolver implements JoinResolver {
    resolve(input: ParsedJoinInput[]): JoinDef[];
}
