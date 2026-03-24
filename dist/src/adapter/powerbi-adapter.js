import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { PBIXAssembler } from "./pbix-assembler.js";
import { PowerBIQualityPipeline } from "./powerbi-quality-pipeline.js";
export class PowerBIAdapter {
    deployConfig;
    constructor(deployConfig = {}) {
        this.deployConfig = deployConfig;
    }
    validate(spec) {
        const errors = [];
        const warnings = [];
        const qualityPipeline = new PowerBIQualityPipeline();
        const quality = qualityPipeline.prepareSpec(spec);
        if (spec.semantic_model.measures.length === 0) {
            warnings.push("No measures found in semantic model.");
        }
        if (spec.export_manifest.dax_measures.length === 0) {
            errors.push("DAX measures are required for Power BI export.");
        }
        if (spec.export_manifest.m_queries.length === 0) {
            errors.push("Power Query M queries are required for Power BI export.");
        }
        for (const issue of quality.issues) {
            errors.push(`${issue.stage}:${issue.code}:${issue.message}`);
        }
        for (const warning of quality.warnings) {
            warnings.push(`${warning.stage}:${warning.code}:${warning.message}`);
        }
        return {
            valid: errors.length === 0,
            errors,
            warnings,
        };
    }
    async build(spec, outputDir) {
        const qualityPipeline = new PowerBIQualityPipeline();
        const quality = qualityPipeline.prepareSpec(spec);
        if (!quality.valid) {
            const details = quality.issues.map((issue) => `${issue.stage}:${issue.code}`).join(", ");
            throw new Error(`Power BI quality pipeline failed before build: ${details}`);
        }
        const assembler = new PBIXAssembler();
        const assembled = assembler.assemble(quality.fixedSpec);
        const pbixIssues = qualityPipeline.validatePbix(assembled.bytes);
        if (pbixIssues.length > 0) {
            const details = pbixIssues.map((issue) => `${issue.stage}:${issue.code}`).join(", ");
            throw new Error(`PBIX validation failed after build: ${details}`);
        }
        await mkdir(outputDir, { recursive: true });
        const artifactPath = path.join(outputDir, assembled.fileName);
        await writeFile(artifactPath, Buffer.from(assembled.bytes));
        return {
            artifactPath,
            artifactBytes: assembled.bytes,
            metadata: {
                target: "powerbi",
                pages: quality.fixedSpec.dashboard_spec.pages.length,
                warnings: quality.warnings.length,
            },
        };
    }
    async deploy(buildResult) {
        if (this.deployConfig.endpoint === undefined || this.deployConfig.endpoint.length === 0) {
            return {
                success: true,
                url: `file://${buildResult.artifactPath}`,
                message: "No remote endpoint configured; artifact kept locally.",
            };
        }
        const response = await fetch(this.deployConfig.endpoint, {
            method: "POST",
            headers: {
                "Content-Type": "application/octet-stream",
                Authorization: this.deployConfig.apiKey ? `Bearer ${this.deployConfig.apiKey}` : "",
            },
            body: Buffer.from(buildResult.artifactBytes),
        });
        if (!response.ok) {
            return {
                success: false,
                message: `Deployment failed with status ${response.status}`,
            };
        }
        const payload = (await response.json());
        const baseResult = {
            success: true,
            message: "Artifact deployed.",
        };
        if (payload.url !== undefined) {
            baseResult.url = payload.url;
        }
        return {
            ...baseResult,
        };
    }
    getCapabilities() {
        return {
            target: "powerbi",
            supportsDeploy: true,
            supportsValidation: true,
            artifactTypes: ["pbix"],
        };
    }
}
