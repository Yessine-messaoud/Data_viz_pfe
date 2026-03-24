import AdmZip from "adm-zip";

import type { AbstractSpec } from "../spec/abstract-spec.js";
import { PBIXTemplate } from "./powerbi-quality-pipeline.js";

export interface PBIXAssemblyResult {
  bytes: Uint8Array;
  fileName: string;
}

export class PBIXAssembler {
  public assemble(spec: AbstractSpec): PBIXAssemblyResult {
    const template = new PBIXTemplate();
    const zip: AdmZip = template.createBaseArchive(spec);

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
