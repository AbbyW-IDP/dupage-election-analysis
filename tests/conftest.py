"""
conftest.py
-----------
Shared pytest fixtures for the dupage_elections test suite.
"""

import pandas as pd
import pytest

from dupage_elections.db import ElectionDatabase


@pytest.fixture
def db():
    """In-memory ElectionDatabase, isolated per test."""
    database = ElectionDatabase(db_path=":memory:")
    yield database
    database.close()


def make_results_df(rows: list[dict]) -> pd.DataFrame:
    """
    Build a minimal results DataFrame suitable for insert_results().
    Any omitted fields default to sensible values.
    """
    defaults = {
        "contest_name_raw": "FOR ATTORNEY GENERAL (Vote For 1)",
        "line_number": 1,
        "choice_name": "Jane Smith",
        "party": "DEM",
        "total_votes": 1000.0,
        "percent_of_votes": 100.0,
        "registered_voters": 10000.0,
        "ballots_cast": 5000.0,
        "num_precinct_total": 10.0,
        "num_precinct_rptg": 10.0,
        "over_votes": 0.0,
        "under_votes": 0.0,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def seed_known_name(db: ElectionDatabase, name: str, year: int = 2022) -> None:
    """Add a known contest name to the registry."""
    db.register_contest_name(name, year)


def seed_results(db: ElectionDatabase, rows: list[dict]) -> None:
    """Insert rows directly into results via insert_results, bypassing file I/O."""
    from dupage_elections.normalize import normalize_contest_name
    for i, row in enumerate(rows, start=1):
        df = pd.DataFrame([{
            "contest_name_raw": row.get("contest_name", row.get("contest_name_raw", "")),
            "line_number": row.get("line_number", i),
            "choice_name": row.get("choice_name", "Candidate"),
            "party": row.get("party"),
            "total_votes": row.get("total_votes", 0),
            "percent_of_votes": row.get("percent_of_votes", 0),
            "registered_voters": row.get("registered_voters", 10000),
            "ballots_cast": row.get("ballots_cast", 5000),
            "num_precinct_total": row.get("num_precinct_total", 10),
            "num_precinct_rptg": row.get("num_precinct_rptg", 10),
            "over_votes": row.get("over_votes", 0),
            "under_votes": row.get("under_votes", 0),
        }])
        # Pre-register the contest name so it isn't flagged as unknown
        contest_name_raw = row.get("contest_name", row.get("contest_name_raw", ""))
        normalized = normalize_contest_name(contest_name_raw)
        db.register_contest_name(normalized, row["year"])
        db.insert_results(df, row["year"], "test_source.csv")
