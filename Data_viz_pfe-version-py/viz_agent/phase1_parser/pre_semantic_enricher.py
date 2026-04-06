from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from viz_agent.models.abstract_spec import (
    ConfidenceScore,
    EnrichedLineageEntry,
    ParsedWorkbook,
    SemanticHint,
    VisualEncoding,
    Worksheet,
)


MEASURE_KEYWORDS = (
    "sales",
    "amount",
    "revenue",
    "profit",
    "cost",
    "margin",
    "price",
    "value",
    "score",
    "qty",
    "quantity",
    "count",
    "total",
    "sum",
    "avg",
    "average",
    "mean",
)

DIMENSION_KEYWORDS = (
    "date",
    "day",
    "month",
    "year",
    "time",
    "country",
    "region",
    "state",
    "city",
    "product",
    "category",
    "customer",
    "segment",
    "type",
    "status",
    "group",
    "name",
    "id",
)

AVERAGE_KEYWORDS = ("avg", "average", "mean")
COUNT_KEYWORDS = ("count", "qty", "quantity", "number", "num", "nb")


@dataclass(frozen=True)
class _ColumnProfile:
    role_hint: str
    aggregation_hint: str
    confidence: float
    data_type: str = ""
    cardinality: int | None = None


class PreSemanticEnricher:
    """Infer lightweight semantic metadata for Phase 1 workbook objects."""

    def enrich(self, workbook: ParsedWorkbook, registry: Any | None = None) -> ParsedWorkbook:
        visual_encoding_map: dict[str, VisualEncoding] = {}
        confidence_map: dict[str, ConfidenceScore] = {}
        aggregate_hints: list[SemanticHint] = []
        aggregate_lineage: list[EnrichedLineageEntry] = []
        warnings: list[str] = list(workbook.validation_warnings)

        for worksheet in workbook.worksheets:
            encoding = self._build_visual_encoding(worksheet)
            worksheet.visual_encoding = encoding
            visual_encoding_map[worksheet.name] = encoding

            if str(worksheet.raw_mark_type or worksheet.mark_type).strip().lower() == "automatic":
                worksheet.mark_type, automatic_warning = self._infer_automatic_mark_type(worksheet, encoding)
                if automatic_warning:
                    warnings.append(f"{worksheet.name}: {automatic_warning}")

            column_profiles = self._build_column_profiles(workbook, worksheet, registry)
            worksheet.semantic_hints = [
                SemanticHint(
                    column=column_name,
                    role_hint=profile.role_hint,
                    aggregation_hint=profile.aggregation_hint,
                    confidence=round(profile.confidence, 3),
                    datasource_name=worksheet.datasource_name,
                    data_type=profile.data_type,
                    cardinality=profile.cardinality,
                    worksheet_role=role_name,
                )
                for column_name, profile, role_name in column_profiles
            ]
            aggregate_hints.extend(worksheet.semantic_hints)

            worksheet.enriched_lineage = [
                EnrichedLineageEntry(
                    column=hint.column,
                    used_in=worksheet.name,
                    role=hint.worksheet_role or self._lineage_role_for_column(worksheet, hint.column),
                    datasource_name=worksheet.datasource_name,
                    confidence=hint.confidence,
                )
                for hint in worksheet.semantic_hints
            ]
            aggregate_lineage.extend(worksheet.enriched_lineage)

            worksheet.validation_warnings = self._worksheet_warnings(workbook, worksheet, worksheet.semantic_hints, registry)
            warnings.extend(worksheet.validation_warnings)

            confidence = self._confidence_for_worksheet(workbook, worksheet, registry)
            worksheet.confidence = confidence
            confidence_map[worksheet.name] = confidence

        workbook.visual_encoding = visual_encoding_map
        workbook.semantic_hints = aggregate_hints
        workbook.enriched_lineage = aggregate_lineage
        workbook.confidence = confidence_map
        workbook.validation_warnings = warnings
        return workbook

    def _build_visual_encoding(self, worksheet: Worksheet) -> VisualEncoding:
        encoding = VisualEncoding()
        if worksheet.cols_shelf:
            encoding.x = worksheet.cols_shelf[0].column
        if worksheet.rows_shelf:
            encoding.y = worksheet.rows_shelf[0].column

        encoding.color = self._resolve_mark_channel(worksheet, "color", 0)
        encoding.size = self._resolve_mark_channel(worksheet, "size", 1)
        encoding.detail = self._resolve_mark_channel(worksheet, "detail", 2)
        return encoding

    def _infer_automatic_mark_type(self, worksheet: Worksheet, encoding: VisualEncoding) -> tuple[str, str]:
        measure_count = self._count_measure_like_fields(worksheet)
        dimension_count = self._count_dimension_like_fields(worksheet)
        explicit_fields = [encoding.x, encoding.y, encoding.color, encoding.size, encoding.detail]
        populated_fields = [field for field in explicit_fields if field]

        if encoding.size and encoding.color and not encoding.x and not encoding.y:
            return "Treemap", "Automatic mark resolved to Treemap from color/size encodings"

        if worksheet.rows_shelf and worksheet.cols_shelf and measure_count >= 1 and dimension_count >= 1:
            return "Bar", "Automatic mark resolved to Bar from rows/cols structure"

        if measure_count == 1 and dimension_count == 0 and len(populated_fields) <= 1:
            return "Text", "Automatic mark resolved to KPI/Text from single-measure layout"

        if measure_count >= 2:
            return "Line", "Automatic mark resolved to Line from multiple measures"

        if worksheet.rows_shelf or worksheet.cols_shelf:
            return "Bar", "Automatic mark resolved to Bar from axis usage"

        return "Text", "Automatic mark resolved to Text fallback"

    def _build_column_profiles(
        self,
        workbook: ParsedWorkbook,
        worksheet: Worksheet,
        registry: Any | None,
    ) -> list[tuple[str, _ColumnProfile, str]]:
        ordered_columns: list[tuple[str, str]] = []
        ordered_columns.extend((ref.column, "x_axis") for ref in worksheet.cols_shelf if ref.column)
        ordered_columns.extend((ref.column, "y_axis") for ref in worksheet.rows_shelf if ref.column)

        for index, ref in enumerate(worksheet.marks_shelf):
            if not ref.column:
                continue
            role = {0: "color", 1: "size", 2: "detail"}.get(index, "detail")
            ordered_columns.append((ref.column, role))

        profiles: list[tuple[str, _ColumnProfile, str]] = []
        seen: set[str] = set()
        for column_name, worksheet_role in ordered_columns:
            normalized = column_name.lower().strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            profile = self._profile_column(workbook, worksheet, column_name, worksheet_role, registry)
            profiles.append((column_name, profile, worksheet_role))
        return profiles

    def _profile_column(
        self,
        workbook: ParsedWorkbook,
        worksheet: Worksheet,
        column_name: str,
        worksheet_role: str,
        registry: Any | None,
    ) -> _ColumnProfile:
        datasource_column = self._find_datasource_column(workbook, worksheet.datasource_name, column_name)
        registry_type, cardinality = self._registry_column_metadata(registry, worksheet.datasource_name, column_name)

        column_label = column_name.lower()
        keyword_role = self._role_from_name(column_label)
        shelf_role = self._role_from_shelf(worksheet_role)
        declared_role = str(getattr(datasource_column, "role", "unknown") or "unknown").lower()
        declared_type = str(getattr(datasource_column, "pbi_type", "") or "")

        role_votes = Counter(
            role
            for role in (declared_role, keyword_role, shelf_role, self._role_from_dtype(registry_type or declared_type))
            if role in {"measure", "dimension"}
        )
        if role_votes:
            role_hint = role_votes.most_common(1)[0][0]
        else:
            role_hint = "unknown"

        aggregation_hint = self._aggregation_from_name(column_label, role_hint)

        confidence = 0.35
        if declared_role in {"measure", "dimension"}:
            confidence += 0.25
        if keyword_role in {"measure", "dimension"} and keyword_role == role_hint:
            confidence += 0.2
        if shelf_role in {"measure", "dimension"} and shelf_role == role_hint:
            confidence += 0.15
        if registry_type:
            confidence += 0.05
        if cardinality is not None:
            confidence += 0.05

        confidence = max(0.0, min(1.0, confidence))

        return _ColumnProfile(
            role_hint=role_hint,
            aggregation_hint=aggregation_hint,
            confidence=confidence,
            data_type=registry_type or declared_type,
            cardinality=cardinality,
        )

    def _worksheet_warnings(
        self,
        workbook: ParsedWorkbook,
        worksheet: Worksheet,
        semantic_hints: list[SemanticHint],
        registry: Any | None,
    ) -> list[str]:
        warnings: list[str] = []
        measure_count = sum(1 for hint in semantic_hints if hint.role_hint == "measure")
        if measure_count == 0:
            warnings.append("visual sans mesure detectee")
        if not any((worksheet.visual_encoding.x, worksheet.visual_encoding.y, worksheet.visual_encoding.color, worksheet.visual_encoding.size, worksheet.visual_encoding.detail)):
            warnings.append("encodage visuel vide")
        raw_mark = str(worksheet.raw_mark_type or "").strip().lower()
        if raw_mark and raw_mark not in {"automatic", "bar", "line", "pie", "treemap", "circle", "map", "text", "square", "gantt"}:
            warnings.append(f"type de marque inconnu: {worksheet.raw_mark_type}")
        if str(worksheet.mark_type or "").strip().lower() in {"", "unknown"}:
            warnings.append("type visuel non resolu")
        if worksheet.datasource_name and registry is not None and not self._datasource_has_reference(workbook, registry, worksheet.datasource_name):
            warnings.append(f"datasource '{worksheet.datasource_name}' non resolue dans le registre")
        return warnings

    def _confidence_for_worksheet(self, workbook: ParsedWorkbook, worksheet: Worksheet, registry: Any | None) -> ConfidenceScore:
        used_columns = self._worksheet_columns(worksheet)
        matched_columns = sum(1 for column_name in used_columns if self._column_exists_in_registry_or_datasource(workbook, worksheet, column_name, registry))

        linkage = matched_columns / len(used_columns) if used_columns else 0.0
        encoding_fields = [worksheet.visual_encoding.x, worksheet.visual_encoding.y, worksheet.visual_encoding.color, worksheet.visual_encoding.size, worksheet.visual_encoding.detail]
        encoding_score = min(1.0, sum(1 for value in encoding_fields if value) / 5.0)

        measure_count = sum(1 for hint in worksheet.semantic_hints if hint.role_hint == "measure")
        visual_score = 0.55
        if str(worksheet.raw_mark_type or "").strip().lower() != "automatic":
            visual_score += 0.2
        if worksheet.visual_encoding.x or worksheet.visual_encoding.y:
            visual_score += 0.1
        if measure_count:
            visual_score += 0.1
        if linkage >= 0.75:
            visual_score += 0.05

        overall = (visual_score * 0.4) + (encoding_score * 0.3) + (linkage * 0.3)
        return ConfidenceScore(
            visual=round(max(0.0, min(1.0, visual_score)), 3),
            encoding=round(max(0.0, min(1.0, encoding_score)), 3),
            datasource_linkage=round(max(0.0, min(1.0, linkage)), 3),
            overall=round(max(0.0, min(1.0, overall)), 3),
        )

    def _lineage_role_for_column(self, worksheet: Worksheet, column_name: str) -> str:
        if any(ref.column == column_name for ref in worksheet.rows_shelf):
            return "y_axis"
        if any(ref.column == column_name for ref in worksheet.cols_shelf):
            return "x_axis"

        for role_name, ref in (worksheet.mark_encodings or {}).items():
            if str(getattr(ref, "column", "") or "") == column_name and role_name in {"color", "size", "detail"}:
                return role_name

        for index, ref in enumerate(worksheet.marks_shelf):
            if ref.column != column_name:
                continue
            return {0: "color", 1: "size", 2: "detail"}.get(index, "detail")
        return "detail"

    def _resolve_mark_channel(self, worksheet: Worksheet, role: str, fallback_index: int) -> str | None:
        mark_encodings = worksheet.mark_encodings or {}
        if mark_encodings:
            explicit_ref = mark_encodings.get(role)
            if explicit_ref is None:
                return None
            explicit_value = str(getattr(explicit_ref, "column", "") or "").strip()
            return explicit_value or None

        explicit_ref = mark_encodings.get(role)
        if explicit_ref is not None:
            explicit_value = str(getattr(explicit_ref, "column", "") or "").strip()
            if explicit_value:
                return explicit_value

        if len(worksheet.marks_shelf) > fallback_index:
            fallback_value = str(getattr(worksheet.marks_shelf[fallback_index], "column", "") or "").strip()
            if fallback_value:
                return fallback_value
        return None

    def _worksheet_columns(self, worksheet: Worksheet) -> list[str]:
        return [ref.column for ref in worksheet.rows_shelf + worksheet.cols_shelf + worksheet.marks_shelf if ref.column]

    def _find_datasource_column(self, workbook: ParsedWorkbook, datasource_name: str, column_name: str) -> Any | None:
        target = datasource_name.strip().lower()
        wanted = column_name.strip().lower()
        if not wanted:
            return None

        for datasource in workbook.datasources:
            ds_name = str(datasource.name or "").strip().lower()
            ds_caption = str(datasource.caption or "").strip().lower()
            if target and target not in {ds_name, ds_caption}:
                continue
            for column in datasource.columns:
                column_label = str(getattr(column, "name", "") or "").strip().lower()
                if column_label == wanted:
                    return column
                if column_label.strip("[]") == wanted.strip("[]"):
                    return column
        return None

    def _column_exists_in_registry_or_datasource(self, workbook: ParsedWorkbook, worksheet: Worksheet, column_name: str, registry: Any | None) -> bool:
        if self._find_datasource_column(workbook, worksheet.datasource_name, column_name) is not None:
            return True

        if registry is None:
            return False

        resolved = getattr(registry, "get", None)
        if callable(resolved) and worksheet.datasource_name:
            candidate = registry.get(worksheet.datasource_name)
            if candidate is not None and self._column_exists_in_frames(candidate.frames.values(), column_name):
                return True

        all_frames = getattr(registry, "all_frames", None)
        if callable(all_frames) and self._column_exists_in_frames(all_frames().values(), column_name):
            return True

        return False

    def _column_exists_in_frames(self, frames: Iterable[pd.DataFrame], column_name: str) -> bool:
        wanted = column_name.strip().lower()
        for frame in frames:
            if frame is None or frame.empty:
                continue
            columns = {str(name).strip().lower(): name for name in frame.columns}
            if wanted in columns:
                return True
        return False

    def _datasource_has_reference(self, workbook: ParsedWorkbook, registry: Any | None, datasource_name: str) -> bool:
        if any(str(ds.name or "").strip().lower() == datasource_name.strip().lower() for ds in workbook.datasources):
            return True
        if registry is None or not datasource_name:
            return False
        getter = getattr(registry, "get", None)
        if callable(getter) and getter(datasource_name) is not None:
            return True
        return False

    def _registry_column_metadata(
        self,
        registry: Any | None,
        datasource_name: str,
        column_name: str,
    ) -> tuple[str, int | None]:
        if registry is None or not datasource_name:
            return "", None

        getter = getattr(registry, "get", None)
        candidate = getter(datasource_name) if callable(getter) else None
        frames = list(getattr(candidate, "frames", {}).values()) if candidate is not None else []
        if not frames:
            all_frames = getattr(registry, "all_frames", None)
            frames = list(all_frames().values()) if callable(all_frames) else []

        wanted = column_name.strip().lower()
        for frame in frames:
            if frame is None or frame.empty:
                continue
            for column in frame.columns:
                if str(column).strip().lower() != wanted:
                    continue
                series = frame[column]
                dtype = str(series.dtype)
                cardinality = int(series.nunique(dropna=True)) if hasattr(series, "nunique") else None
                return dtype, cardinality
        return "", None

    def _role_from_name(self, column_name: str) -> str:
        lowered = column_name.lower()
        if any(keyword in lowered for keyword in MEASURE_KEYWORDS):
            return "measure"
        if any(keyword in lowered for keyword in DIMENSION_KEYWORDS):
            return "dimension"
        return "unknown"

    def _role_from_shelf(self, worksheet_role: str) -> str:
        if worksheet_role in {"x_axis", "color", "detail"}:
            return "dimension"
        if worksheet_role in {"y_axis", "size"}:
            return "measure"
        return "unknown"

    def _role_from_dtype(self, dtype_text: str) -> str:
        lowered = str(dtype_text or "").lower()
        if any(token in lowered for token in ("int", "float", "double", "decimal", "numeric", "real")):
            return "measure"
        if any(token in lowered for token in ("date", "datetime", "time")):
            return "dimension"
        return "unknown"

    def _aggregation_from_name(self, column_name: str, role_hint: str) -> str:
        lowered = column_name.lower()
        if any(keyword in lowered for keyword in AVERAGE_KEYWORDS):
            return "avg"
        if any(keyword in lowered for keyword in COUNT_KEYWORDS):
            return "count"
        if role_hint == "measure":
            return "sum"
        return "none"

    def _count_measure_like_fields(self, worksheet: Worksheet) -> int:
        return sum(1 for ref in self._worksheet_refs(worksheet) if self._role_from_name(ref.column) == "measure")

    def _count_dimension_like_fields(self, worksheet: Worksheet) -> int:
        return sum(1 for ref in self._worksheet_refs(worksheet) if self._role_from_name(ref.column) == "dimension")

    def _worksheet_refs(self, worksheet: Worksheet) -> list[Any]:
        return list(worksheet.rows_shelf) + list(worksheet.cols_shelf) + list(worksheet.marks_shelf)


def build_visual_encoding(rows: list[Any], cols: list[Any], marks: list[Any]) -> VisualEncoding:
    worksheet = Worksheet(
        name="__encoding__",
        mark_type="Text",
        rows_shelf=list(rows),
        cols_shelf=list(cols),
        marks_shelf=list(marks),
    )
    return PreSemanticEnricher()._build_visual_encoding(worksheet)


def infer_automatic_mark_type(worksheet: Worksheet) -> str:
    encoding = PreSemanticEnricher()._build_visual_encoding(worksheet)
    return PreSemanticEnricher()._infer_automatic_mark_type(worksheet, encoding)[0]
