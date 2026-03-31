from __future__ import annotations

from viz_agent.models.abstract_spec import DataSource, JoinDef


class JoinResolver:
    def resolve(self, datasources: list[DataSource]) -> list[JoinDef]:
        joins: list[JoinDef] = []
        for index, datasource in enumerate(datasources):
            if index + 1 < len(datasources):
                left = datasource.name or datasource.caption or f"table_{index}"
                right_ds = datasources[index + 1]
                right = right_ds.name or right_ds.caption or f"table_{index + 1}"
                joins.append(
                    JoinDef(
                        id=f"join_{index}",
                        left_table=left,
                        right_table=right,
                        left_col="id",
                        right_col="id",
                    )
                )
        return joins
