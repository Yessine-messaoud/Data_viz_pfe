from __future__ import annotations

REPORT_REQUIRED_PATHS = [
    "r:DataSources/r:DataSource",
    "r:DataSets/r:DataSet",
    "r:ReportSections/r:ReportSection/r:Body/r:ReportItems",
    "r:ReportSections/r:ReportSection/r:Page",
]

DATASOURCE_REQUIRED_CHILDREN = [
    "ConnectionProperties",
]

DATASET_REQUIRED_CHILDREN = [
    "Fields",
    "Query",
]

QUERY_REQUIRED_CHILDREN = [
    "DataSourceName",
    "CommandText",
]

FIELD_REQUIRED_CHILDREN = [
    "DataField",
]

TABLIX_REQUIRED_CHILDREN = [
    "TablixBody",
    "DataSetName",
]
