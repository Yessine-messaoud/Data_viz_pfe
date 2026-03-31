"""Legacy CSV loader wrapper."""

from viz_agent.phase0_extraction.readers.csv_loader import CSVLoader as _CSVLoader


class CSVLoader(_CSVLoader):
    """Backward-compatible CSV loader API."""

    def extract_from_twbx(self, twbx_path: str):
        return self.extract_all_tables(twbx_path)
