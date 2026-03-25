from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from viz_agent.models.abstract_spec import ColumnDef, TableRef

try:
    import pantab

    PANTAB_AVAILABLE = True
except ImportError:
    PANTAB_AVAILABLE = False


class HyperExtractor:
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

                    if PANTAB_AVAILABLE:
                        tables = pantab.frames_from_hyper(str(hyper_path))
                        results[hyper_name] = {str(table_name): frame for table_name, frame in tables.items()}
                    else:
                        results[hyper_name] = self._extract_native(hyper_path)

        return results

    def _extract_native(self, hyper_path: Path) -> dict[str, pd.DataFrame]:
        try:
            from tableauhyperapi import Connection, HyperProcess, Telemetry
        except ImportError as exc:
            raise RuntimeError(
                "Hyper extraction requires pantab or tableauhyperapi. Install one of them."
            ) from exc

        frames: dict[str, pd.DataFrame] = {}
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as process:
            with Connection(process.endpoint, str(hyper_path)) as conn:
                catalog = conn.catalog
                for schema in catalog.get_schema_names():
                    for table in catalog.get_table_names(schema):
                        rows = conn.execute_list_query(f"SELECT * FROM {table}")
                        cols = [col.name.unescaped for col in catalog.get_table_definition(table).columns]
                        frames[str(table)] = pd.DataFrame(rows, columns=cols)
        return frames

    def get_schema(self, df: pd.DataFrame, table_name: str) -> TableRef:
        type_map = {
            "int64": "int64",
            "float64": "double",
            "object": "text",
            "datetime64[ns]": "dateTime",
            "bool": "boolean",
        }

        columns = [
            ColumnDef(
                name=col,
                pbi_type=type_map.get(str(df[col].dtype), "text"),
                role="measure" if str(df[col].dtype) in ("int64", "float64") else "dimension",
            )
            for col in df.columns
        ]

        return TableRef(id=table_name, name=table_name, columns=columns, row_count=len(df))
