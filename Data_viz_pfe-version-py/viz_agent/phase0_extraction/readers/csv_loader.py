from __future__ import annotations

import zipfile
from pathlib import Path
import pandas as pd

class CSVLoader:
    def extract_from_twbx(self, twbx_path: str) -> dict[str, pd.DataFrame]:
        """Backward-compatible alias for legacy phase0_data API."""
        return self.extract_all_tables(twbx_path)

    def extract_all_tables(self, twbx_path: str) -> dict[str, pd.DataFrame]:
        """Extract all CSV tables from a Tableau TWBX archive."""
        results: dict[str, pd.DataFrame] = {}
        with zipfile.ZipFile(twbx_path) as archive:
            csv_files = [name for name in archive.namelist() if name.endswith(".csv")]
            for csv_name in csv_files:
                with archive.open(csv_name) as raw_csv:
                    try:
                        dataframe = pd.read_csv(raw_csv, encoding="utf-8")
                    except UnicodeDecodeError:
                        raw_csv.seek(0)
                        dataframe = pd.read_csv(raw_csv, encoding="latin-1")
                    results[csv_name] = dataframe
        return results
