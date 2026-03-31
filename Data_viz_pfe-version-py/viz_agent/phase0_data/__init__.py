"""Compatibility layer for legacy `phase0_data` imports.

This package re-exports the phase 0 data access APIs from `phase0_extraction`
to keep older modules/tests functional during the migration.
"""

from .csv_loader import CSVLoader
from .data_source_registry import DataSourceRegistry, ResolvedDataSource
from .hyper_extractor import HyperExtractor, PANTAB_AVAILABLE

__all__ = [
    "CSVLoader",
    "DataSourceRegistry",
    "ResolvedDataSource",
    "HyperExtractor",
    "PANTAB_AVAILABLE",
]
