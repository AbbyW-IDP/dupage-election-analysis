"""
Tests for dupage_elections.loader (ElectionLoader)
"""

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from dupage_elections.loader import (
    ElectionLoader,
    _normalize_csv_columns,
    _normalize_excel_columns,
    _year_from_filename,
)
from tests.conftest import make_results_df, seed_known_name


# ---------------------------------------------------------------------------
# _year_from_filename
# ---------------------------------------------------------------------------

class TestYearFromFilename:

    def test_extracts_year_from_standard_name(self):
        assert _year_from_filename("summary_2026.csv") == 2026

    def test_extracts_year_from_prefix(self):
        assert _year_from_filename("2022_results.csv") == 2022

    def test_extracts_year_embedded_in_name(self):
        assert _year_from_filename("results2018final.csv") == 2018

    def test_extracts_election_year_from_date_suffixed_name(self):
        # Election year leads the filename; results date follows
        assert _year_from_filename("2022-general-primary-2022-07-19.csv") == 2022

    def test_extracts_year_when_election_and_results_date_differ(self):
        # Election year should win over a later results certification date
        assert _year_from_filename("2022-general-primary-2023-01-15.csv") == 2022

    def test_returns_none_when_no_year(self):
        assert _year_from_filename("results.csv") is None

    def test_returns_none_for_non_20xx_year(self):
        assert _year_from_filename("results_1998.csv") is None


# ---------------------------------------------------------------------------
# _normalize_csv_columns
# ---------------------------------------------------------------------------

class TestNormalizeCsvColumns:

    def test_lowercases_columns(self):
        df = pd.DataFrame({"Contest Name": [], "Party Name": []})
        result = _normalize_csv_columns(df)
        assert "contest_name_raw" in result.columns
        assert "party" in result.columns

    def test_replaces_spaces_with_underscores(self):
        df = pd.DataFrame({"total votes": [], "party name": []})
        result = _normalize_csv_columns(df)
        assert "total_votes" in result.columns

    def test_renames_contest_name_to_raw(self):
        df = pd.DataFrame({"contest name": []})
        result = _normalize_csv_columns(df)
        assert "contest_name_raw" in result.columns
        assert "contest_name" not in result.columns

    def test_renames_party_name_to_party(self):
        df = pd.DataFrame({"party name": []})
        result = _normalize_csv_columns(df)
        assert "party" in result.columns
        assert "party_name" not in result.columns


# ---------------------------------------------------------------------------
# _normalize_excel_columns
# ---------------------------------------------------------------------------

class TestNormalizeExcelColumns:

    def test_sets_contest_name_raw_from_contestMixed(self):
        df = pd.DataFrame({"contestMixed": ["FOR SENATOR - D*"], "party": ["DEM"]})
        result = _normalize_excel_columns(df)
        assert result["contest_name_raw"].iloc[0] == "FOR SENATOR - D*"

    def test_renames_choice_name(self):
        df = pd.DataFrame({"contestMixed": ["X"], "choice name": ["Jane Smith"]})
        result = _normalize_excel_columns(df)
        assert "choice_name" in result.columns

    def test_renames_total_votes(self):
        df = pd.DataFrame({"contestMixed": ["X"], "total votes": [1000]})
        result = _normalize_excel_columns(df)
        assert "total_votes" in result.columns


# ---------------------------------------------------------------------------
# ElectionLoader.load_csv
# ---------------------------------------------------------------------------

CSV_HEADER = "line number,contest name,choice name,party name,total votes,percent of votes,registered voters,ballots cast,num Precinct total,num Precinct rptg,over votes,under votes"


def write_csv(tmp_path: Path, rows: list[str], filename: str = "summary_2026.csv") -> Path:
    p = tmp_path / filename
    p.write_text(CSV_HEADER + "\n" + "\n".join(rows))
    return p


class TestLoaderLoadCsv:

    def test_inserts_rows(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
            "2,FOR SENATOR (Vote For 1),John Doe,R,4000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        inserted, _ = loader.load_csv(path, year=2026)
        assert inserted == 2

    def test_normalizes_contest_name(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR ATTORNEY GENERAL (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        row = db.query("SELECT contest_name FROM results").iloc[0]
        assert row["contest_name"] == "FOR ATTORNEY GENERAL"

    def test_normalizes_party_codes(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
            "2,FOR SENATOR (Vote For 1),John Doe,R,4000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        parties = set(db.query("SELECT party FROM results")["party"])
        assert parties == {"DEM", "REP"}

    def test_registers_source_after_load(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        assert db.is_source_loaded("summary_2026.csv")

    def test_stores_source_filename(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        row = db.query("SELECT source_file FROM results").iloc[0]
        assert row["source_file"] == "summary_2026.csv"

    def test_flags_unrecognized_contest_names(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR BRAND NEW CONTEST (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        _, new_names = loader.load_csv(path, year=2026)
        assert "FOR BRAND NEW CONTEST" in new_names

    def test_no_flags_when_all_names_known(self, db, tmp_path):
        seed_known_name(db, "FOR ATTORNEY GENERAL", 2022)
        path = write_csv(tmp_path, [
            "1,FOR ATTORNEY GENERAL (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        _, new_names = loader.load_csv(path, year=2026)
        assert new_names == []

    def test_returns_correct_row_count(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
            "2,FOR SENATOR (Vote For 1),John Doe,R,4000,100.0,50000,10000,10,10,0,0",
            "3,FOR GOVERNOR (Vote For 1),Alice Brown,D,9000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        inserted, _ = loader.load_csv(path, year=2026)
        assert inserted == 3

    def test_contest_id_format(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2026.csv")
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        row = db.query("SELECT contest_id, year, line_number FROM results").iloc[0]
        assert row["contest_id"] == f"2026-{int(row['line_number'])}"

    def test_contest_id_uses_year_and_line_number(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
            "2,FOR SENATOR (Vote For 1),John Doe,R,4000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2022.csv")
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2022)
        rows = db.query("SELECT contest_id, line_number FROM results ORDER BY line_number")
        assert rows.iloc[0]["contest_id"] == "2022-1"
        assert rows.iloc[1]["contest_id"] == "2022-2"

    def test_contest_ids_are_unique_per_row(self, db, tmp_path):
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
            "2,FOR SENATOR (Vote For 1),John Doe,R,4000,100.0,50000,10000,10,10,0,0",
            "3,FOR GOVERNOR (Vote For 1),Alice Brown,D,9000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2026.csv")
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        ids = db.query("SELECT contest_id FROM results")["contest_id"]
        assert ids.nunique() == 3

    def test_uses_override_for_contest_name(self, db, tmp_path):
        db.add_override(
            "FOR SENATOR (Vote For 1)",
            "FOR UNITED STATES SENATOR",
        )
        seed_known_name(db, "FOR UNITED STATES SENATOR", 2022)
        path = write_csv(tmp_path, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ])
        loader = ElectionLoader(db)
        loader.load_csv(path, year=2026)
        row = db.query("SELECT contest_name FROM results").iloc[0]
        assert row["contest_name"] == "FOR UNITED STATES SENATOR"


# ---------------------------------------------------------------------------
# ElectionLoader.sync_sources
# ---------------------------------------------------------------------------

class TestLoaderSyncSources:

    def test_loads_new_csv_files(self, db, tmp_path):
        sources = tmp_path / "sources"
        sources.mkdir()
        write_csv(sources, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2026.csv")
        loader = ElectionLoader(db)
        results = loader.sync_sources(sources)
        assert "summary_2026.csv" in results

    def test_skips_already_loaded_files(self, db, tmp_path):
        sources = tmp_path / "sources"
        sources.mkdir()
        write_csv(sources, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2026.csv")
        loader = ElectionLoader(db)
        loader.sync_sources(sources)
        results = loader.sync_sources(sources)
        assert "summary_2026.csv" not in results

    def test_loads_multiple_files(self, db, tmp_path):
        sources = tmp_path / "sources"
        sources.mkdir()
        for year in [2022, 2026]:
            write_csv(sources, [
                f"1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
            ], filename=f"summary_{year}.csv")
        loader = ElectionLoader(db)
        results = loader.sync_sources(sources)
        assert len(results) == 2

    def test_skips_files_without_year_in_name(self, db, tmp_path):
        sources = tmp_path / "sources"
        sources.mkdir()
        write_csv(sources, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ], filename="results.csv")
        loader = ElectionLoader(db)
        results = loader.sync_sources(sources)
        assert "results.csv" not in results

    def test_raises_if_sources_dir_missing(self, db, tmp_path):
        loader = ElectionLoader(db)
        with pytest.raises(FileNotFoundError):
            loader.sync_sources(tmp_path / "nonexistent")

    def test_returns_empty_dict_when_no_new_files(self, db, tmp_path):
        sources = tmp_path / "sources"
        sources.mkdir()
        loader = ElectionLoader(db)
        results = loader.sync_sources(sources)
        assert results == {}

    def test_database_entries_persist_after_second_sync(self, db, tmp_path):
        """Entries from the first sync should still be in the DB after a second sync."""
        sources = tmp_path / "sources"
        sources.mkdir()
        write_csv(sources, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2026.csv")
        loader = ElectionLoader(db)
        loader.sync_sources(sources)
        row_count_after_first = len(db.query("SELECT * FROM results"))
        loader.sync_sources(sources)
        row_count_after_second = len(db.query("SELECT * FROM results"))
        assert row_count_after_first == row_count_after_second

    def test_infers_year_from_filename(self, db, tmp_path):
        sources = tmp_path / "sources"
        sources.mkdir()
        write_csv(sources, [
            "1,FOR SENATOR (Vote For 1),Jane Smith,D,5000,100.0,50000,10000,10,10,0,0",
        ], filename="summary_2022.csv")
        loader = ElectionLoader(db)
        loader.sync_sources(sources)
        row = db.query("SELECT year FROM results").iloc[0]
        assert row["year"] == 2022
