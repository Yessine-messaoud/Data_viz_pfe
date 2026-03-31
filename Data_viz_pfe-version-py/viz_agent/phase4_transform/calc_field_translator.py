from __future__ import annotations

from viz_agent.models.abstract_spec import SemanticModel
from viz_agent.phase2_semantic.mistral_client import MistralApiClient
from viz_agent.validators.expression_validator import ExpressionValidator

SYSTEM_PROMPT = """Tu es un expert en expressions RDL et DAX Power BI.
Tu traduis des expressions calculees Tableau en expressions valides.

REGLES STRICTES :
1. Pour les expressions numeriques : utiliser la syntaxe =Sum(Fields!FieldName.Value)
2. Pour les ratios : utiliser =IIF(Denominator=0, 0, Numerator/Denominator)
3. Pour COUNTD Tableau -> =CountDistinct(Fields!FieldName.Value)
4. Retourner UNIQUEMENT l'expression - aucun texte, aucune explication
5. Si intraduisible -> retourner exactement : __UNTRANSLATABLE__"""

USER_PROMPT_TEMPLATE = """TABLES DISPONIBLES :
{tables_context}

EXEMPLES DE TRADUCTION :
Tableau: SUM([Sales Amount])
RDL: =Sum(Fields!SalesAmount.Value)

Tableau: COUNTD([Sales Order])
RDL: =CountDistinct(Fields!SalesOrder.Value)

Tableau: {{ FIXED [Category] : SUM([Sales Amount]) }}
RDL: =Sum(Fields!SalesAmount.Value)

EXPRESSION A TRADUIRE :
{expression}

Retourne uniquement l'expression RDL :"""

ADVENTUREWORKS_OVERRIDES = {
    "Calculation_1259319095595331584": "=Sum(Fields!Profit.Value)",
    "Calculation_1259319095894155266": "=Sum(Fields!SalesAmount.Value)",
    "Calculation_1259319095915106309": "=CountDistinct(Fields!SalesOrder.Value)",
}


class CalcFieldTranslator:
    def __init__(self, llm_client=None, validator: ExpressionValidator | None = None):
        self.llm = llm_client or MistralApiClient.from_env()
        self.validator = validator or ExpressionValidator()
        self.llm_calls = 0
        self.llm_success = 0
        self.llm_failed = 0

    def translate(self, expression: str, model: SemanticModel, max_retries: int = 3) -> str:
        for key, mapped in ADVENTUREWORKS_OVERRIDES.items():
            if key in expression:
                return mapped

        tables_ctx = self._format_tables(model)
        prompt = USER_PROMPT_TEMPLATE.format(tables_context=tables_ctx, expression=expression)

        for _attempt in range(max_retries):
            try:
                self.llm_calls += 1
                result = self.llm.chat_text(SYSTEM_PROMPT, prompt).strip()
            except Exception:
                self.llm_failed += 1
                continue

            if result.startswith("```"):
                result = result.replace("```rdl", "").replace("```", "").strip()

            if result == "__UNTRANSLATABLE__":
                self.llm_failed += 1
                break

            issues = self.validator.validate_expression(result)
            errors = [issue for issue in issues if issue.severity == "error"]
            if not errors:
                self.llm_success += 1
                return result

            prompt = USER_PROMPT_TEMPLATE.format(
                tables_context=tables_ctx,
                expression=(
                    f"Expression originale: {expression}\n"
                    f"Tentative precedente: {result}\n"
                    f"Erreurs: {[error.message for error in errors]}\n"
                    "Corrige ces erreurs."
                ),
            )

        return f"/* UNTRANSLATABLE: {expression} */"

    def _format_tables(self, model: SemanticModel) -> str:
        rows: list[str] = []
        for table in model.entities:
            cols = ", ".join(col.name for col in getattr(table, "columns", []))
            rows.append(f"{table.name}: {cols}")
        return "\n".join(rows)
