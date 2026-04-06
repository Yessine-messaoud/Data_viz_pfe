from __future__ import annotations

import json
import logging

from viz_agent.models.abstract_spec import Measure, ParsedWorkbook
from viz_agent.phase2_semantic.llm_fallback_client import LLMFallbackClient


ENRICHER_SYSTEM_PROMPT = """
Tu es un expert en modelisation de donnees Power BI.
Tu enrichis un SemanticModel extrait d'un workbook Tableau.
Reponds UNIQUEMENT en JSON valide, sans markdown, sans explication.
""".strip()


ENRICHER_USER_PROMPT = """
Tables et colonnes extraites :
{tables_json}

Champs calcules Tableau :
{calculated_fields_json}

Encodages charts/worksheets extraits du TWB :
{worksheets_json}

Dashboards et composition :
{dashboards_json}

Taches :
1. Pour chaque colonne avec un nom technique, propose un label lisible
2. Identifie les mesures metier manquantes depuis les champs calcules et encodages charts
3. Identifie les hierarchies temporelles (Year > Quarter > Month > Date)
4. Propose les roles semantiques des colonnes utilises dans les charts (measure/dimension)

Retourne ce JSON exact :
{{
    "column_labels": {{"table.colonne": "Label lisible"}},
    "suggested_measures": [{{"name": "...", "expression": "...", "source": "calc_field_name"}}],
    "hierarchies": [{{"name": "...", "table": "...", "levels": ["Year","Quarter","Month","Date"]}}],
    "column_roles": {{"table.colonne": "measure|dimension"}}
}}
""".strip()


class SemanticEnricher:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or LLMFallbackClient.from_env()
        self.logger = logging.getLogger(__name__)

    def enrich(self, workbook: ParsedWorkbook, schema_map):
        tables_payload = self._build_tables_payload(schema_map)
        calc_payload = [
            {"name": calc.name, "expression": calc.expression}
            for calc in workbook.calculated_fields
        ]
        worksheets_payload = [
            {
                "name": ws.name,
                "mark_type": ws.mark_type,
                "datasource": ws.datasource_name,
                "rows": [{"table": r.table, "column": r.column} for r in ws.rows_shelf],
                "cols": [{"table": c.table, "column": c.column} for c in ws.cols_shelf],
                "marks": [{"table": m.table, "column": m.column} for m in ws.marks_shelf],
            }
            for ws in workbook.worksheets
        ]
        dashboards_payload = [
            {
                "name": dashboard.name,
                "worksheets": dashboard.worksheets,
            }
            for dashboard in workbook.dashboards
        ]

        user_prompt = ENRICHER_USER_PROMPT.format(
            tables_json=json.dumps(tables_payload, ensure_ascii=True),
            calculated_fields_json=json.dumps(calc_payload, ensure_ascii=True),
            worksheets_json=json.dumps(worksheets_payload, ensure_ascii=True),
            dashboards_json=json.dumps(dashboards_payload, ensure_ascii=True),
        )

        response: dict = {}
        llm_provider = "none"
        llm_error = ""
        try:
            response = self.llm_client.chat_json(
                system_prompt=ENRICHER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            llm_provider = str(getattr(self.llm_client, "last_provider", "") or "unknown")
        except Exception as exc:
            self.logger.warning("LLM enrichment failed, using heuristic fallback: %s", exc)
            response = {}
            llm_provider = str(getattr(self.llm_client, "last_provider", "") or "none")
            llm_error = str(getattr(self.llm_client, "last_error", "") or str(exc))

        suggested_measures: list[Measure] = []
        for measure in response.get("suggested_measures", []):
            name = str(measure.get("name", "")).strip() or "calculated_measure"
            expression = str(measure.get("expression", "")).strip() or "0"
            source = str(measure.get("source", "")).strip()
            suggested_measures.append(
                Measure(name=name, expression=expression, tableau_expression=source)
            )

        if not suggested_measures:
            self.logger.warning("LLM returned no suggested measures, using heuristic fallback.")
            suggested_measures = self._build_heuristic_measures(workbook, schema_map)

        column_labels = response.get("column_labels", {})
        hierarchies = response.get("hierarchies", [])
        column_roles = response.get("column_roles", {})

        class EnrichmentResult:
            def __init__(self, suggested, labels, hierarchy, roles, provider, error):
                self.column_labels = labels
                self.suggested_measures = suggested
                self.hierarchies = hierarchy
                self.column_roles = roles
                self.llm_provider = provider
                self.llm_error = error

        return EnrichmentResult(suggested_measures, column_labels, hierarchies, column_roles, llm_provider, llm_error)

    def _build_heuristic_measures(self, workbook: ParsedWorkbook, schema_map) -> list[Measure]:
        measures: list[Measure] = []
        seen: set[str] = set()

        # Priority 1: existing calculated fields become semantic measures.
        for calc in getattr(workbook, "calculated_fields", []) or []:
            name = str(getattr(calc, "name", "") or "").strip()
            expression = str(getattr(calc, "expression", "") or "").strip()
            if not name or not expression:
                continue
            key = name.lower()
            if key in seen:
                continue
            measures.append(Measure(name=name, expression=expression, tableau_expression=name))
            seen.add(key)

        # Priority 2: infer from schema columns explicitly marked as measure.
        tables = getattr(schema_map, "tables", []) or []
        for table in tables:
            for col in getattr(table, "columns", []) or []:
                col_name = str(getattr(col, "name", "") or "").strip()
                role = str(getattr(col, "role", "unknown") or "unknown").lower()
                if not col_name:
                    continue
                if role != "measure" and not self._looks_numeric_measure(col_name):
                    continue
                if self._looks_key(col_name):
                    continue

                measure_name = f"Sum {col_name}"
                key = measure_name.lower()
                if key in seen:
                    continue
                measures.append(
                    Measure(
                        name=measure_name,
                        expression=f"SUM([{col_name}])",
                        tableau_expression=col_name,
                    )
                )
                seen.add(key)

        # Last-resort fallback to keep pipeline running.
        if not measures:
            measures.append(Measure(name="Row Count", expression="COUNT(*)", tableau_expression="row_count"))

        return measures

    def _looks_key(self, name: str) -> bool:
        lowered = name.lower()
        return lowered.endswith("key") or lowered.endswith("_id") or lowered == "id"

    def _looks_numeric_measure(self, name: str) -> bool:
        lowered = name.lower()
        keywords = ("amount", "sales", "revenue", "profit", "cost", "price", "qty", "quantity", "count", "tax")
        return any(keyword in lowered for keyword in keywords)

    def _build_tables_payload(self, schema_map):
        if schema_map is None or not hasattr(schema_map, "tables"):
            return []
        payload = []
        for table in schema_map.tables:
            payload.append(
                {
                    "name": table.name,
                    "columns": [
                        {"name": col.name, "role": col.role, "type": col.pbi_type}
                        for col in table.columns
                    ],
                }
            )
        return payload
