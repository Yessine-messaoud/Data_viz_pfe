"""Legacy Hyper extractor wrapper with compatibility hooks."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pandas as pd

try:
    import pantab

    PANTAB_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional dependency
    pantab = None
    PANTAB_AVAILABLE = False


class HyperExtractor:
    """Backward-compatible Hyper extractor API.

    Returns a mapping keyed by Hyper filename to keep old call sites working.
    """

    def _extract_native(self, hyper_path: str) -> dict[str, pd.DataFrame]:
        if not PANTAB_AVAILABLE:
            raise RuntimeError(
                "Hyper extraction requires pantab or tableauhyperapi. Install one of them."
            )
        return pantab.frames_from_hyper(hyper_path)

    def extract_from_twbx(self, twbx_path: str) -> dict[str, dict[str, pd.DataFrame]]:
        results: dict[str, dict[str, pd.DataFrame]] = {}
        with zipfile.ZipFile(twbx_path) as archive:
            hyper_files = [name for name in archive.namelist() if name.endswith(".hyper")]
            if not hyper_files:
                return results
            with tempfile.TemporaryDirectory() as temp_dir:
                for hyper_name in hyper_files:
                    archive.extract(hyper_name, temp_dir)
                    hyper_path = Path(temp_dir) / hyper_name
                    tables = self._extract_native(str(hyper_path))
                    results[hyper_name] = {str(table): frame for table, frame in tables.items()}
        return results
