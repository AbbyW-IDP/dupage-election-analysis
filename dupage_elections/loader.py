"""
loader.py
---------
ElectionLoader: reads source files and loads them into an ElectionDatabase.

Supports:
  - CSV files (raw election exports)
  - Excel files with a 'data' tab (historical workbook)
  - Automatic syncing of a sources/ directory
"""

import re
from pathlib import Path

import pandas as pd

from dupage_elections.db import ElectionDatabase


def _normalize_csv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize CSV column names and rename to internal conventions."""
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df.rename(columns={
        "contest_name": "contest_name_raw",
        "party_name":   "party",
    })


def _normalize_excel_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize columns from the historical Excel workbook's data tab.
    Uses contestMixed (original mixed-case name) as the raw contest name.
    """
    df = df.copy()
    df["contest_name_raw"] = df["contestMixed"]
    return df.rename(columns={
        "line number":        "line_number",
        "choice name":        "choice_name",
        "total votes":        "total_votes",
        "percent of votes":   "percent_of_votes",
        "registered voters":  "registered_voters",
        "ballots cast":       "ballots_cast",
        "num precinct total": "num_precinct_total",
        "num precinct rptg":  "num_precinct_rptg",
        "over votes":         "over_votes",
        "under votes":        "under_votes",
    })


def _year_from_filename(filename: str) -> int | None:
    """
    Extract the election year from a filename.

    Tries two strategies in order:
      1. A 4-digit year at the very start of the filename stem, e.g.
         '2022-general-primary-2022-07-19.csv' -> 2022
      2. The first 20xx year anywhere in the filename, e.g.
         'summary_2026.csv' -> 2026

    Returns None if no year found.
    """
    stem = Path(filename).stem
    # Strategy 1: year at the start of the stem (handles date-suffixed names)
    match = re.match(r'(20\d{2})', stem)
    if match:
        return int(match.group(1))
    # Strategy 2: first 20xx year anywhere in the name
    match = re.search(r'(20\d{2})', stem)
    return int(match.group(1)) if match else None


class ElectionLoader:
    """
    Reads election source files and loads them into an ElectionDatabase.

    Args:
        db: An ElectionDatabase instance to load data into.

    Usage:
        loader = ElectionLoader(db)
        loader.load_csv(Path("sources/summary_2026.csv"), year=2026)
        loader.load_excel(Path("comparison_14-26.xlsx"))
        loader.sync_sources(Path("sources/"))
    """

    def __init__(self, db: ElectionDatabase) -> None:
        self._db = db

    def load_csv(self, path: Path, year: int) -> tuple[int, list[str]]:
        """
        Load a single election CSV into the database.

        Args:
            path: Path to the CSV file.
            year: Election year for this file.

        Returns:
            (rows_inserted, new_unrecognized_contest_names)
        """
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="windows-1252")
        df = _normalize_csv_columns(df)
        inserted, new_names = self._db.insert_results(df, year, path.name)
        self._db.register_source(path.name, year)
        return inserted, new_names

    def load_excel(self, path: Path) -> dict[int, tuple[int, list[str]]]:
        """
        Load the historical Excel workbook (all years in the 'data' tab).

        Loads each year separately so contest name registration is year-aware.

        Args:
            path: Path to the Excel workbook.

        Returns:
            Dict mapping year -> (rows_inserted, new_unrecognized_contest_names)
        """
        df = pd.read_excel(path, sheet_name="data")
        df = _normalize_excel_columns(df)

        results = {}
        for year, group in df.groupby("year"):
            inserted, new_names = self._db.insert_results(
                group.copy(), int(year), path.name
            )
            self._db.register_source(f"{path.name}:{year}", int(year))
            results[int(year)] = (inserted, new_names)
        return results

    def sync_sources(self, sources_dir: Path) -> dict[str, tuple[int, list[str]]]:
        """
        Scan a directory for CSV source files and load any that haven't
        been loaded yet. Files are identified by name, so renaming a file
        will cause it to be reloaded. Database entries from previously
        loaded files are never removed.

        CSV filenames must contain a 4-digit year (e.g. summary_2026.csv).
        Files without a recognizable year are skipped with a warning.

        Args:
            sources_dir: Path to the directory containing CSV source files.

        Returns:
            Dict mapping filename -> (rows_inserted, new_unrecognized_contest_names)
            for each newly loaded file. Already-loaded files are not included.
        """
        if not sources_dir.exists():
            raise FileNotFoundError(f"Sources directory not found: {sources_dir}")

        results = {}
        csv_files = sorted(sources_dir.glob("*.csv"))

        for path in csv_files:
            if self._db.is_source_loaded(path.name):
                continue

            year = _year_from_filename(path.name)
            if year is None:
                print(f"  Skipping {path.name}: could not determine year from filename.")
                continue

            inserted, new_names = self.load_csv(path, year)
            results[path.name] = (inserted, new_names)

        return results
