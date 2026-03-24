export type StableUuid = string;
export type Semver = string;
export type Sha256Hex = string;
export type VisualType = "bar" | "barChart" | "line" | "lineChart" | "area" | "pie" | "scatter" | "table" | "tableEx" | "map" | "filledMap" | "kpi" | "card" | "treemap" | "heatmap" | "combo" | "custom";
export type FilterOperator = "equals" | "not_equals" | "in" | "not_in" | "gt" | "gte" | "lt" | "lte" | "between" | "contains" | "starts_with" | "ends_with";
export type JoinType = "inner" | "left" | "right" | "full";
export type RelationshipCardinality = "one-to-one" | "one-to-many" | "many-to-one" | "many-to-many";
export type RelationshipCrossFilterDirection = "single" | "both";
export interface ColumnRef {
    table: string;
    column: string;
}
export interface GridPosition {
    row: number;
    column: number;
    row_span: number;
    column_span: number;
}
export interface DataBindingAxes {
    x?: ColumnRef;
    y?: ColumnRef;
    color?: ColumnRef;
    size?: ColumnRef;
    tooltip?: ColumnRef;
}
export interface DataBinding {
    axes: DataBindingAxes;
}
export interface FilterRef {
    column: ColumnRef;
    operator: FilterOperator;
    value: string | number | boolean | Array<string | number | boolean>;
}
export interface VisualSpec {
    id: string;
    source_worksheet: string;
    type: VisualType;
    position: GridPosition;
    data_binding: DataBinding;
    filters?: FilterRef[];
    title?: string;
}
export interface ThemeConfig {
    name: string;
    palette: string[];
    font_family?: string;
    font_size?: number;
    background_color?: string;
}
export interface RefreshPolicy {
    mode: "manual" | "scheduled" | "live";
    interval_minutes?: number;
    timezone?: string;
}
export interface DashboardPage {
    id: string;
    name: string;
    visuals: VisualSpec[];
}
export interface DashboardSpec {
    pages: DashboardPage[];
    global_filters: FilterRef[];
    theme: ThemeConfig;
    refresh_policy: RefreshPolicy;
}
export interface TableRef {
    id: string;
    name: string;
    schema?: string;
}
export interface JoinKey {
    left: ColumnRef;
    right: ColumnRef;
}
export interface JoinDef {
    id: string;
    left_table: string;
    right_table: string;
    type: JoinType;
    keys: JoinKey[];
}
export interface ColumnUsage {
    visual_id: string;
    column: ColumnRef;
    usage: "axis" | "filter" | "tooltip" | "measure" | "grouping";
}
export interface VisualLineage {
    columns: ColumnRef[];
    joins_used: string[];
    filters: FilterRef[];
}
export interface DataLineageSpec {
    tables: TableRef[];
    joins: JoinDef[];
    columns_used: ColumnUsage[];
    visual_column_map: Record<string, VisualLineage>;
    full_tables?: TableRef[];
    sampled_rows?: Record<string, Array<Record<string, string | number | boolean | null>>>;
    full_table_profiles?: Array<{
        table_name: string;
        columns: Array<{
            name: string;
            type: string;
        }>;
        sample_data: Array<Record<string, string | number | boolean | null>>;
        source: "xml" | "csv" | "hyper";
    }>;
}
export interface SemanticField {
    name: string;
    source?: ColumnRef;
    description?: string;
}
export interface MeasureDef {
    name: string;
    expression: string;
    format_string?: string;
    source_columns?: ColumnRef[];
}
export interface HierarchyLevel {
    name: string;
    column: ColumnRef;
}
export interface HierarchyDef {
    name: string;
    levels: HierarchyLevel[];
}
export interface RelationshipDef {
    from: ColumnRef;
    to: ColumnRef;
    cardinality: RelationshipCardinality;
    cross_filter_direction: RelationshipCrossFilterDirection;
}
export interface GlossaryEntry {
    term: string;
    definition: string;
}
export interface SemanticModel {
    entities: SemanticField[];
    measures: MeasureDef[];
    dimensions: SemanticField[];
    hierarchies: HierarchyDef[];
    relationships: RelationshipDef[];
    glossary: GlossaryEntry[];
    fact_table: string;
    grain: string;
}
export interface ModelConfig {
    dataset_name: string;
    compatibility_level?: number;
    culture?: string;
}
export interface DaxMeasure {
    name: string;
    expression: string;
}
export interface MQuery {
    name: string;
    query: string;
}
export interface PostExportHook {
    name: string;
    enabled: boolean;
    config?: Record<string, string | number | boolean>;
}
export interface ExportManifest {
    target: "powerbi";
    model_config: ModelConfig;
    dax_measures: DaxMeasure[];
    m_queries: MQuery[];
    post_export_hooks: PostExportHook[];
}
export interface BuildIntent {
    request_id?: string;
    description?: string;
    target: "powerbi";
    modifications?: string[];
}
export interface WorkbookInput {
    raw: string | Uint8Array;
    source_name?: string;
}
export interface BuildLogEntry {
    level: "info" | "warn" | "error";
    message: string;
    timestamp: string;
}
export interface SpecWarning {
    code: string;
    message: string;
}
export interface AbstractSpec {
    id: StableUuid;
    version: Semver;
    source_fingerprint: Sha256Hex;
    dashboard_spec: DashboardSpec;
    semantic_model: SemanticModel;
    data_lineage: DataLineageSpec;
    export_manifest: ExportManifest;
    build_log: BuildLogEntry[];
    warnings: SpecWarning[];
}
