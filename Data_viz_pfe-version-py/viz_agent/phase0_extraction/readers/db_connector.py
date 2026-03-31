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
    def extract_all_tables(self, config: ConnectionConfig) -> dict[str, pd.DataFrame]:
        """Extract all tables from a SQL database connection."""
        import sqlalchemy
        engine = sqlalchemy.create_engine(config.connection_string or self._build_url(config))
        results: dict[str, pd.DataFrame] = {}
        with engine.connect() as conn:
            table_names = conn.execute("SELECT table_name FROM INFORMATION_SCHEMA.TABLES WHERE table_type='BASE TABLE'").fetchall()
            for (table_name,) in table_names:
                dataframe = pd.read_sql(f"SELECT * FROM {table_name}", conn)
                results[table_name] = dataframe
        return results

    def _build_url(self, config: ConnectionConfig) -> str:
        return (
            f"{config.type}://{config.username}:{config.password}"
            f"@{config.host}:{config.port}/{config.database}"
        )
