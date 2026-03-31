from __future__ import annotations

import json

from viz_agent.models.abstract_spec import Measure, ParsedWorkbook
from viz_agent.phase2_semantic.mistral_client import MistralApiClient


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
        self.llm_client = llm_client or MistralApiClient.from_env()

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

        response = self.llm_client.chat_json(
            system_prompt=ENRICHER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        suggested_measures: list[Measure] = []
        for measure in response.get("suggested_measures", []):
            name = str(measure.get("name", "")).strip() or "calculated_measure"
            expression = str(measure.get("expression", "")).strip() or "0"
            source = str(measure.get("source", "")).strip()
            suggested_measures.append(
                Measure(name=name, expression=expression, tableau_expression=source)
            )

        if not suggested_measures:
            # Strictly based on Mistral response contract; if no measure returned, fail fast.
            raise RuntimeError("Mistral enrichment returned no suggested_measures")

        column_labels = response.get("column_labels", {})
        hierarchies = response.get("hierarchies", [])
        column_roles = response.get("column_roles", {})

        class EnrichmentResult:
            def __init__(self, suggested, labels, hierarchy, roles):
                self.column_labels = labels
                self.suggested_measures = suggested
                self.hierarchies = hierarchy
                self.column_roles = roles

        return EnrichmentResult(suggested_measures, column_labels, hierarchies, column_roles)

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
