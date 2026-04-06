from __future__ import annotations

from typing import Any

from viz_agent.validators.contracts import ValidationIssueV2


class SemanticValidator:
    name = "semantic"

    def validate(self, data: dict[str, Any], context: dict[str, Any]) -> list[ValidationIssueV2]:
        issues: list[ValidationIssueV2] = []

        semantic = (data.get("semantic_model") or {}) if "semantic_model" in data else (context.get("semantic_model") or {})
        if not isinstance(semantic, dict):
            return issues

        fact_table = str(semantic.get("fact_table", "") or "").strip()
        if not fact_table:
            issues.append(
                ValidationIssueV2(
                    type="semantic",
                    severity="error",
                    code="SM001",
                    message="fact_table vide.",
                    location="semantic_model.fact_table",
                    suggestion="Renseigner une table de faits issue du lineage.",
                )
            )

        entities = semantic.get("entities", [])
        entity_names = {
            str((entity or {}).get("name", "")).strip()
            for entity in entities
            if isinstance(entity, dict)
        }
        entity_names.discard("")
        if fact_table and entity_names and fact_table not in entity_names:
            issues.append(
                ValidationIssueV2(
                    type="semantic",
                    severity="warning",
                    code="SM002",
                    message=f"fact_table '{fact_table}' absente des entites.",
                    location="semantic_model.fact_table",
                    suggestion="Verifier la detection de table de faits ou normaliser les noms.",
                )
            )

        measures = semantic.get("measures", [])
        if not isinstance(measures, list) or not measures:
            issues.append(
                ValidationIssueV2(
                    type="semantic",
                    severity="warning",
                    code="SM003",
                    message="Aucune mesure detectee dans le modele semantique.",
                    location="semantic_model.measures",
                    suggestion="Ajouter au moins une mesure metier pour les visuals aggreges.",
                )
            )

        dashboard = data.get("dashboard_spec") or {}
        pages = dashboard.get("pages", []) if isinstance(dashboard, dict) else []
        for p_idx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            for v_idx, visual in enumerate(page.get("visuals", []) or []):
                if not isinstance(visual, dict):
                    continue
                vtype = str(visual.get("type", "")).strip().lower()
                if vtype == "chart":
                    issues.append(
                        ValidationIssueV2(
                            type="semantic",
                            severity="error",
                            code="SM004",
                            message="Type visuel generique 'chart' interdit dans la couche abstraite.",
                            location=f"dashboard_spec.pages[{p_idx}].visuals[{v_idx}].type",
                            suggestion="Utiliser un type semantique explicite (bar/line/pie/treemap/scatter...).",
                        )
                    )

        return issues
