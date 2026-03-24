export declare function runSqlServerRdlDemo(workspaceRoot: string): Promise<{
    workbookPath: string;
    pbixPath: string;
    rdlPath: string;
    sqlServer: string;
    sqlDatabase: string;
    selectedWorksheet: string;
}>;
