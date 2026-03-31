from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ColumnProfile:
    name: str
    inferred_dtype: str
    role: str
    distinct_count: int
    null_ratio: float
    sample_values: List[Any]


class ColumnProfiler:
    def __init__(self) -> None:
        self.logger = logger

    def profile_dataset(self, dataset_name: str, df: pd.DataFrame) -> List[ColumnProfile]:
        if df is None or df.empty:
            self.logger.warning("Profiling skipped for '%s': empty dataframe", dataset_name)
            return []

        profiles: List[ColumnProfile] = []
        for col in df.columns:
            series = df[col]
            inferred_dtype = str(series.dtype)
            role = self._classify_column(col, series)
            distinct_count = int(series.nunique(dropna=True))
            null_ratio = float(series.isna().mean()) if len(series) else 0.0
            sample_values = self._sample_values(series)

            profiles.append(
                ColumnProfile(
                    name=col,
                    inferred_dtype=inferred_dtype,
                    role=role,
                    distinct_count=distinct_count,
                    null_ratio=null_ratio,
                    sample_values=sample_values,
                )
            )

        self.logger.info(
            "Profiling dataset '%s': %d columns, roles=%s",
            dataset_name,
            len(profiles),
            self._role_summary(profiles),
        )
        return profiles

    def _classify_column(self, col_name: str, series: pd.Series) -> str:
        name_lower = col_name.lower()
        if "date" in name_lower or pd.api.types.is_datetime64_any_dtype(series):
            return "date"
        if pd.api.types.is_numeric_dtype(series):
            return "measure"
        return "dimension"

    def _sample_values(self, series: pd.Series, k: int = 3) -> List[Any]:
        vals = series.dropna().head(k).tolist()
        return [self._safe_value(v) for v in vals]

    def _safe_value(self, value: Any) -> Any:
        try:
            if pd.api.types.is_float(value) and pd.isna(value):
                return None
            return value
        except Exception:
            return None

    def _role_summary(self, profiles: List[ColumnProfile]) -> Dict[str, int]:
        summary: Dict[str, int] = {"measure": 0, "dimension": 0, "date": 0}
        for p in profiles:
            if p.role in summary:
                summary[p.role] += 1
        return summary
