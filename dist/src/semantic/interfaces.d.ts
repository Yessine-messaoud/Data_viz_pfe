import type { ColumnRef, DataLineageSpec, JoinDef, SemanticModel, VisualLineage, VisualSpec } from "../spec/abstract-spec.js";
export interface ParsedJoinInput {
    id: string;
    leftTable: string;
    rightTable: string;
    joinType: "inner" | "left" | "right" | "full";
    keys: Array<{
        leftColumn: string;
        rightColumn: string;
    }>;
}
export interface ParsedWorkbookSemanticInput {
    columns: Array<{
        table: string;
        column: string;
        inferredRole: "dimension" | "measure";
    }>;
    visuals: VisualSpec[];
    joins: ParsedJoinInput[];
    glossaryCandidates?: Array<{
        term: string;
        definition: string;
    }>;
}
export interface SchemaMapper {
    mapTypes(tableauType: string): string;
    mapVisualType(tableauVisualType: string): VisualSpec["type"];
}
export interface SemanticEnricher {
    enrich(base: SemanticModel, context: SemanticEnrichmentContext): Promise<SemanticEnrichmentResult>;
}
export interface SemanticEnrichmentContext {
    glossary: Record<string, string>;
    ambiguousColumns: ColumnRef[];
    complexCalcs: string[];
}
export interface SemanticEnrichmentResult {
    renamedDimensions: Array<{
        from: string;
        to: string;
        confidence: number;
    }>;
    suggestedMeasures: Array<{
        name: string;
        expression: string;
        confidence: number;
    }>;
    disambiguationNotes: string[];
}
export interface CalcFieldTranslator {
    translateTableauFormula(formula: string): {
        daxExpression: string;
        confidence: number;
        usedLlm: boolean;
    };
}
export interface JoinResolver {
    resolve(input: ParsedJoinInput[]): JoinDef[];
}
export interface SemanticMergerInput {
    deterministic: SemanticModel;
    llm: SemanticEnrichmentResult;
    glossaryOverrides: Record<string, string>;
}
export interface SemanticMerger {
    merge(input: SemanticMergerInput): SemanticModel;
}
export interface GraphNode {
    id: string;
    label: "table" | "column" | "measure" | "visual";
    weight: number;
    metadata?: Record<string, string | number | boolean>;
}
export interface GraphEdge {
    from: string;
    to: string;
    type: "has_column" | "joins" | "uses" | "depends_on" | "filters";
    weight: number;
}
export interface SemanticGraph {
    nodes: GraphNode[];
    edges: GraphEdge[];
}
export interface SemanticGraphRepository {
    resetGraph(): Promise<void>;
    upsertGraph(graph: SemanticGraph): Promise<void>;
    shortestPath(from: string, to: string): Promise<string[]>;
    detectCycles(): Promise<string[][]>;
    upstreamNodes(nodeId: string): Promise<string[]>;
}
export interface SemanticGraphBuilder {
    build(model: SemanticModel, lineage: DataLineageSpec): Promise<SemanticGraph>;
}
export interface LineageQueryService {
    getTablesForVisual(visualId: string): Promise<string[]>;
    getJoin(joinId: string): JoinDef | undefined;
    getVisualsForColumn(column: ColumnRef): Promise<string[]>;
    getPathBetweenColumns(from: ColumnRef, to: ColumnRef): Promise<string[]>;
}
export interface SemanticHooks {
    analyzeImpact(changedNodeIds: string[]): Promise<Record<string, string[]>>;
    validateNoCyclesBeforePbixAssembly(): Promise<{
        valid: boolean;
        cycles: string[][];
    }>;
    buildLlmContextForComplexCalc(calcExpression: string, visualLineage: VisualLineage): Promise<string>;
}
