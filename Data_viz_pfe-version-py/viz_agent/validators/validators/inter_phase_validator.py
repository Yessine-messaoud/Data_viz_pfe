from __future__ import annotations

from typing import Any

from viz_agent.validators.contracts import ValidationIssueV2


class InterPhaseValidator:
    name = "inter_phase"

    def validate(self, data: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssueV2]:
        issues: list[ValidationIssueV2] = []

        dashboard = data.get("dashboard_spec") or {}
        semantic = data.get("semantic_model") or context.get("semantic_model") or {}
        datasets = data.get("rdl_datasets") or context.get("rdl_datasets") or []

        semantic_columns = self._semantic_columns(semantic)
        dataset_fields = self._dataset_fields(datasets)

        pages = (dashboard.get("pages") or []) if isinstance(dashboard, dict) else []
        if not isinstance(pages, list):
            return issues
        for p_idx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            visuals = (page or {}).get("visuals") or []
            if not isinstance(visuals, list):
                continue
            for v_idx, visual in enumerate(visuals):
                if not isinstance(visual, dict):
                    continue
                bindings = ((visual or {}).get("data_binding") or {}).get("axes") or {}
                if not isinstance(bindings, dict):
                    continue
                for axis_name, axis_value in bindings.items():
                    col = ""
                    if isinstance(axis_value, dict):
                        col = str(axis_value.get("column", "") or axis_value.get("name", "")).strip()
                    if not col:
                        continue

                    if semantic_columns and col not in semantic_columns:
                        issues.append(
                            ValidationIssueV2(
                                type="inter_phase",
                                severity="warning",
                                code="IP001",
                                message=f"Champ '{col}' non trouve dans semantic_model.entities.",
                                location=f"dashboard_spec.pages[{p_idx}].visuals[{v_idx}].data_binding.axes.{axis_name}",
                                suggestion="Aligner les axes visuals avec les colonnes semantiques.",
                            )
                        )
                    if dataset_fields and col not in dataset_fields:
                        issues.append(
                            ValidationIssueV2(
                                type="inter_phase",
                                severity="warning",
                                code="IP002",
                                message=f"Champ '{col}' non trouve dans les fields RDL datasets.",
                                location=f"dashboard_spec.pages[{p_idx}].visuals[{v_idx}].data_binding.axes.{axis_name}",
                                suggestion="Verifier mapping Phase 4 vers rdl_datasets fields.",
                            )
                        )

        return issues

    def _semantic_columns(self, semantic: dict[str, Any]) -> set[str]:
        cols: set[str] = set()
        entities = semantic.get("entities", []) if isinstance(semantic, dict) else []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            for col in entity.get("columns", []) or []:
                if isinstance(col, dict):
                    name = str(col.get("name", "")).strip()
                    if name:
                        cols.add(name)
        return cols

    def _dataset_fields(self, datasets: list[Any]) -> set[str]:
        cols: set[str] = set()
        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            for field in ds.get("fields", []) or []:
                if isinstance(field, dict):
                    name = str(field.get("name", "")).strip()
                    if name:
                        cols.add(name)
        return cols
