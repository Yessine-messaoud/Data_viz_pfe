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

try:
    from tableauhyperapi import Connection, HyperProcess, Telemetry
    TABLEAUHYPERAPI_AVAILABLE = True
except ImportError:
    TABLEAUHYPERAPI_AVAILABLE = False

class HyperExtractor:
    def _extract_native(self, hyper_path: Path) -> dict[str, pd.DataFrame]:
        if PANTAB_AVAILABLE:
            tables = pantab.frames_from_hyper(str(hyper_path))
            return {str(table_name): frame for table_name, frame in tables.items()}

        if TABLEAUHYPERAPI_AVAILABLE:
            return self._extract_with_tableauhyperapi(hyper_path)

        raise RuntimeError("Hyper extraction requires pantab or tableauhyperapi. Install one of them.")

    def _extract_with_tableauhyperapi(self, hyper_path: Path) -> dict[str, pd.DataFrame]:
        results: dict[str, pd.DataFrame] = {}
        with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
            with Connection(endpoint=hyper.endpoint, database=str(hyper_path)) as connection:
                for schema_name in connection.catalog.get_schema_names():
                    table_names = connection.catalog.get_table_names(schema_name)
                    for table_name in table_names:
                        definition = connection.catalog.get_table_definition(table_name)
                        columns = [
                            col.name.unescaped if hasattr(col.name, "unescaped") else str(col.name)
                            for col in definition.columns
                        ]
                        rows = connection.execute_list_query(f"SELECT * FROM {table_name}")
                        results[str(table_name)] = pd.DataFrame(rows, columns=columns)
        return results

    def extract_from_twbx(self, twbx_path: str) -> dict[str, dict[str, pd.DataFrame]]:
        """Backward-compatible API returning tables grouped by hyper file."""
        results: dict[str, dict[str, pd.DataFrame]] = {}
        with zipfile.ZipFile(twbx_path) as archive:
            hyper_files = [name for name in archive.namelist() if name.endswith(".hyper")]
            if not hyper_files:
                return results
            with tempfile.TemporaryDirectory() as temp_dir:
                for hyper_name in hyper_files:
                    archive.extract(hyper_name, temp_dir)
                    hyper_path = Path(temp_dir) / hyper_name
                    results[hyper_name] = self._extract_native(hyper_path)
        return results

    def extract_all_tables(self, twbx_path: str) -> dict[str, pd.DataFrame]:
        """Extract all tables from all Hyper files in a Tableau TWBX archive."""
        results: dict[str, pd.DataFrame] = {}
        for tables in self.extract_from_twbx(twbx_path).values():
            results.update(tables)
        return results
