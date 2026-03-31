from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
import pandas as pd

try:
    import pantab
    PANTAB_AVAILABLE = True
except ImportError:
    PANTAB_AVAILABLE = False

class HyperExtractor:
    def extract_all_tables(self, twbx_path: str) -> dict[str, pd.DataFrame]:
        """Extract all tables from all Hyper files in a Tableau TWBX archive."""
        results: dict[str, pd.DataFrame] = {}
        with zipfile.ZipFile(twbx_path) as archive:
            hyper_files = [name for name in archive.namelist() if name.endswith(".hyper")]
            if not hyper_files:
                return results
            with tempfile.TemporaryDirectory() as temp_dir:
                for hyper_name in hyper_files:
                    archive.extract(hyper_name, temp_dir)
                    hyper_path = Path(temp_dir) / hyper_name
                    if PANTAB_AVAILABLE:
                        tables = pantab.frames_from_hyper(str(hyper_path))
                        for table_name, frame in tables.items():
                            results[str(table_name)] = frame
                    else:
                        # Optionally implement fallback with tableauhyperapi
                        pass
        return results
