from __future__ import annotations

from viz_agent.models.abstract_spec import ColumnDef, DataLineageSpec, JoinDef, TableRef
from viz_agent.phase6_lineage.lineage_service import LineageQueryService


def test_lineage_service_exports_tables_and_joins() -> None:
    lineage = DataLineageSpec(
        tables=[TableRef(id="t1", name="sales_data", columns=[ColumnDef(name="SalesAmount")])],
        joins=[
            JoinDef(
                id="j1",
                left_table="sales_data",
                right_table="customer_data",
                left_col="CustomerKey",
                right_col="CustomerKey",
            )
        ],
    )

    service = LineageQueryService(lineage)

    assert service.list_tables() == ["sales_data"]
    assert len(service.list_joins()) == 1
    assert service.build_select_all("sales_data") == "SELECT * FROM sales_data"
    assert "sales_data" in service.to_json()
