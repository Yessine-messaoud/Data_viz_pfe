#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import date, datetime, time
from decimal import Decimal


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime, time, Decimal)):
        return str(value)
    return str(value)


def _column_name(column):
    name = getattr(column, "name", None)
    if name is None:
        return "unknown"
    unescaped = getattr(name, "unescaped", None)
    if unescaped is not None:
        return str(unescaped)
    return str(name)


def _table_name(table_name_obj):
    try:
        schema = getattr(table_name_obj, "schema_name", None)
        name = getattr(table_name_obj, "name", None)
        if schema is not None and name is not None:
            schema_value = getattr(schema, "unescaped", schema)
            name_value = getattr(name, "unescaped", name)
            return f"{schema_value}.{name_value}"
    except Exception:
        pass
    return str(table_name_obj)


def main():
    parser = argparse.ArgumentParser(description="Read Hyper extract and return table profiles")
    parser.add_argument("hyper_path")
    parser.add_argument("--head", type=int, default=5)
    args = parser.parse_args()

    try:
        from tableauhyperapi import Connection, CreateMode, HyperProcess, Telemetry
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"tableauhyperapi import failed: {exc}"}))
        return 2

    try:
        tables = []
        with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
            with Connection(endpoint=hyper.endpoint, database=args.hyper_path, create_mode=CreateMode.NONE) as connection:
                schema_names = connection.catalog.get_schema_names()
                for schema_name in schema_names:
                    table_names = connection.catalog.get_table_names(schema_name)
                    for table_name_obj in table_names:
                        table_def = connection.catalog.get_table_definition(table_name_obj)
                        columns = [
                            {
                                "name": _column_name(column),
                                "type": str(getattr(column, "type", "unknown")),
                            }
                            for column in table_def.columns
                        ]

                        query = f"SELECT * FROM {table_name_obj} LIMIT {max(args.head, 1)}"
                        rows = []
                        for row in connection.execute_list_query(query):
                            row_dict = {}
                            for idx, column in enumerate(columns):
                                value = row[idx] if idx < len(row) else None
                                row_dict[column["name"]] = _serialize(value)
                            rows.append(row_dict)

                        tables.append(
                            {
                                "table_name": _table_name(table_name_obj),
                                "columns": columns,
                                "sample_data": rows,
                                "source": "hyper",
                            }
                        )

        print(json.dumps({"ok": True, "tables": tables}))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
