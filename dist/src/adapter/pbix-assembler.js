import { PBIXTemplate } from "./powerbi-quality-pipeline.js";
export class PBIXAssembler {
    assemble(spec) {
        const template = new PBIXTemplate();
        const zip = template.createBaseArchive(spec);
        const dataModel = {
            semantic_model: spec.semantic_model,
            export_manifest: spec.export_manifest,
        };
        const report = {
            pages: spec.dashboard_spec.pages,
            global_filters: spec.dashboard_spec.global_filters,
        };
        const theme = {
            name: spec.dashboard_spec.theme.name,
            palette: spec.dashboard_spec.theme.palette,
        };
        const connections = {
            tables: spec.data_lineage.tables,
            joins: spec.data_lineage.joins,
        };
        zip.addFile("DataModel/model.json", Buffer.from(JSON.stringify(dataModel, null, 2), "utf8"));
        zip.addFile("Report/layout.json", Buffer.from(JSON.stringify(report, null, 2), "utf8"));
        zip.addFile("theme.json", Buffer.from(JSON.stringify(theme, null, 2), "utf8"));
        zip.addFile("connections.json", Buffer.from(JSON.stringify(connections, null, 2), "utf8"));
        return {
            bytes: new Uint8Array(zip.toBuffer()),
            fileName: `artifact-${spec.id}.pbix`,
        };
    }
}
