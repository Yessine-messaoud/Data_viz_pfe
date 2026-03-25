from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ConnectionConfig:
    type: str
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    connection_string: str = ""


class DBConnector:
    def connect_and_sample(
        self,
        config: ConnectionConfig,
        tables: list[str],
        sample_rows: int = 1000,
    ) -> dict[str, pd.DataFrame]:
        import sqlalchemy

        engine = sqlalchemy.create_engine(config.connection_string or self._build_url(config))
        results: dict[str, pd.DataFrame] = {}
        with engine.connect() as conn:
            for table in tables:
                dataframe = pd.read_sql(f"SELECT * FROM {table} LIMIT {sample_rows}", conn)
                results[table] = dataframe
        return results

    def _build_url(self, config: ConnectionConfig) -> str:
        return (
            f"{config.type}://{config.username}:{config.password}"
            f"@{config.host}:{config.port}/{config.database}"
        )
