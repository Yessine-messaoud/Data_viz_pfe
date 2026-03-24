export interface FullPipelineDemoOutput {
    abstractJsonPath: string;
    visualHtmlPath: string;
    artifactPath: string;
    lineagePath: string;
    abstractSpecPath: string;
    paginatedRdlPath: string;
    extractionProofPath: string;
    pbixPath?: string;
    deployUrl?: string;
}
export declare function runFullPipelineDemo(workspaceRoot: string): Promise<FullPipelineDemoOutput>;
