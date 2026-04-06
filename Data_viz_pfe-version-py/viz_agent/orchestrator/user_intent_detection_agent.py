from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class IntentDetectionResult:
    intent_type: str
    action: str
    output_format: str
    modifications: list[str]
    chart_specs: list[str]
    confidence: float
    language: str


class UserIntentDetectionAgent:
    """Agentic user intent detector (FR/EN) supervised by the orchestrator layer."""

    _FR_HINTS = {
        "convert": ["convertir", "conversion", "transformer", "exporter"],
        "modify": ["modifier", "modification", "ajuster", "changer", "avec modification"],
        "scratch": ["from scratch", "a partir de zero", "creer", "creation", "nouveau dashboard"],
        "no_change": ["sans modification", "sans changer", "as is", "tel quel", "inchangé"],
    }

    _EN_HINTS = {
        "convert": ["convert", "conversion", "transform", "export"],
        "modify": ["modify", "modification", "adjust", "change", "with modifications"],
        "scratch": ["from scratch", "create dashboard", "new dashboard", "build dashboard"],
        "no_change": ["without changes", "no changes", "as is", "unchanged"],
    }

    _OUTPUT_FORMATS = ["rdl", "pbix", "pdf", "png", "html", "json", "yaml", "xlsx", "csv"]

    def detect(
        self,
        user_request: str,
        *,
        input_path: Path,
        output_path: Path,
        intent_type_override: str | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        constraints = dict(constraints or {})
        query = str(user_request or "").strip()

        if intent_type_override:
            detected = IntentDetectionResult(
                intent_type=intent_type_override,
                action=self._action_from_type(intent_type_override, query),
                output_format=output_path.suffix.lower().lstrip(".") or "rdl",
                modifications=self._extract_modifications(query),
                chart_specs=self._extract_chart_specs(query),
                confidence=0.65,
                language=self._detect_language(query),
            )
        else:
            detected = self._agentic_detect(query, input_path=input_path, output_path=output_path)

        constraints.setdefault("requested_output_format", detected.output_format)
        if detected.modifications:
            constraints.setdefault("requested_modifications", detected.modifications)
        if detected.chart_specs:
            constraints.setdefault("requested_chart_specs", detected.chart_specs)

        return {
            "type": detected.intent_type,
            "action": detected.action,
            "constraints": constraints,
            "pipeline_target": "tableau_to_rdl" if detected.intent_type != "generation" else "dashboard_generation",
            "artifacts": {
                "input_format": input_path.suffix.lower().lstrip("."),
                "output_format": detected.output_format,
            },
            "intent_detection": {
                "agent": "user_intent_detection_agent",
                "supervised_by": "orchestrator_agent",
                "confidence": detected.confidence,
                "language": detected.language,
                "request": query,
                "modifications": detected.modifications,
                "chart_specs": detected.chart_specs,
                "agentic": True,
            },
        }

    def _agentic_detect(self, query: str, *, input_path: Path, output_path: Path) -> IntentDetectionResult:
        text = query.lower()
        lang = self._detect_language(query)

        convert = self._has_any(text, self._FR_HINTS["convert"] + self._EN_HINTS["convert"])
        modify = self._has_any(text, self._FR_HINTS["modify"] + self._EN_HINTS["modify"])
        scratch = self._has_any(text, self._FR_HINTS["scratch"] + self._EN_HINTS["scratch"])
        no_change = self._has_any(text, self._FR_HINTS["no_change"] + self._EN_HINTS["no_change"])

        if scratch:
            intent_type = "generation"
            action = "create_dashboard_from_scratch"
            confidence = 0.9
        elif convert and modify and not no_change:
            intent_type = "optimization"
            action = "convert_bi_with_modifications"
            confidence = 0.88
        elif convert or no_change or (input_path.suffix.lower() in {".twb", ".twbx"} and output_path.suffix.lower() == ".rdl"):
            intent_type = "conversion"
            action = "convert_dashboard_without_changes" if no_change or not modify else "convert_bi_with_modifications"
            confidence = 0.82 if no_change else 0.8
        else:
            intent_type = "generation"
            action = "create_dashboard_from_scratch"
            confidence = 0.55

        out_fmt = self._detect_output_format(text, output_path)

        return IntentDetectionResult(
            intent_type=intent_type,
            action=action,
            output_format=out_fmt,
            modifications=self._extract_modifications(query),
            chart_specs=self._extract_chart_specs(query),
            confidence=confidence,
            language=lang,
        )

    def _action_from_type(self, intent_type: str, query: str) -> str:
        lower = str(query or "").lower()
        if intent_type == "conversion":
            if self._has_any(lower, self._FR_HINTS["no_change"] + self._EN_HINTS["no_change"]):
                return "convert_dashboard_without_changes"
            return "convert_bi_with_modifications" if self._extract_modifications(query) else "convert_dashboard_without_changes"
        if intent_type == "optimization":
            return "convert_bi_with_modifications"
        if intent_type == "generation":
            return "create_dashboard_from_scratch"
        if intent_type == "analysis":
            return "analyze_dashboard_request"
        return "export_rdl"

    def _detect_output_format(self, text: str, output_path: Path) -> str:
        for fmt in self._OUTPUT_FORMATS:
            if re.search(rf"\b{re.escape(fmt)}\b", text):
                return fmt
        suffix = output_path.suffix.lower().lstrip(".")
        return suffix or "rdl"

    def _extract_modifications(self, query: str) -> list[str]:
        text = str(query or "")
        parts = re.split(r"[;\n]|\bet\b|\band\b", text, flags=re.IGNORECASE)
        items: list[str] = []
        for part in parts:
            p = part.strip(" -:\t")
            if not p:
                continue
            lower = p.lower()
            if any(k in lower for k in ("modifier", "modif", "change", "ajouter", "remove", "supprimer", "rename", "filtre", "filter")):
                items.append(p)
        return items[:12]

    def _extract_chart_specs(self, query: str) -> list[str]:
        text = str(query or "")
        chart_words = [
            "bar", "line", "pie", "treemap", "scatter", "area", "map", "tablix",
            "histogram", "waterfall", "donut", "gauge", "kpi",
            "bar chart", "line chart", "pie chart", "stacked",
        ]
        specs: list[str] = []
        for word in chart_words:
            if re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE):
                specs.append(word)
        # preserve order / unique
        seen: set[str] = set()
        ordered: list[str] = []
        for s in specs:
            if s in seen:
                continue
            seen.add(s)
            ordered.append(s)
        return ordered[:20]

    def _detect_language(self, query: str) -> str:
        text = str(query or "").lower()
        fr_markers = [" le ", " la ", " les ", " des ", " avec ", "sans", "modifier", "creer", "tableau"]
        en_markers = [" the ", " with ", " without ", " modify", "create", "dashboard", "from scratch"]
        fr_hits = sum(1 for m in fr_markers if m in f" {text} ")
        en_hits = sum(1 for m in en_markers if m in f" {text} ")
        if fr_hits > en_hits:
            return "fr"
        if en_hits > fr_hits:
            return "en"
        return "mixed"

    @staticmethod
    def _has_any(text: str, keywords: list[str]) -> bool:
        return any(k in text for k in keywords)
