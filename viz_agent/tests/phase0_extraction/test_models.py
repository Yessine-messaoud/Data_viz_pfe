from __future__ import annotations

from viz_agent.phase0_extraction.models import Column, MetadataModel, Relationship, Table


def test_metadata_model_minimal() -> None:
    model = MetadataModel(
        source_type="hyper",
        source_path="/tmp/source.twbx",
        tables=[
            Table(
                name="Extract",
                schema_name="Extract",
                columns=[Column(name="Country", type="VARCHAR", table="Extract")],
            )
        ],
        relationships=[
            Relationship(
                source_table="Orders",
                source_column="CustomerID",
                target_table="Customer",
                target_column="CustomerID",
                type="inferred_suffix",
            )
        ],
    )

    assert model.metadata_version == "v1"
    assert model.tables[0].columns[0].role == "unknown"
