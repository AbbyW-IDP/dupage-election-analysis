"""
Tests for dupage_elections.db (ElectionDatabase)
"""

import sqlite3
from pathlib import Path

import pytest

from dupage_elections.db import ElectionDatabase, DEFAULT_DB_PATH


class TestSchema:

    def test_creates_results_table(self, db):
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        assert "results" in tables["name"].values

    def test_creates_contest_names_table(self, db):
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        assert "contest_names" in tables["name"].values

    def test_creates_contest_name_flags_table(self, db):
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        assert "contest_name_flags" in tables["name"].values

    def test_creates_contest_name_overrides_table(self, db):
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        assert "contest_name_overrides" in tables["name"].values

    def test_creates_loaded_sources_table(self, db):
        tables = db.query("SELECT name FROM sqlite_master WHERE type='table'")
        assert "loaded_sources" in tables["name"].values

    def test_idempotent(self, db):
        """Creating a second ElectionDatabase on the same path should not raise."""
        db2 = ElectionDatabase(":memory:")
        db2.close()

    def test_results_has_source_file_column(self, db):
        cols = db.query("PRAGMA table_info(results)")
        assert "source_file" in cols["name"].values

    def test_results_has_required_columns(self, db):
        cols = set(db.query("PRAGMA table_info(results)")["name"])
        expected = {
            "id", "contest_id", "line_number", "year", "source_file",
            "contest_name_raw", "contest_name", "choice_name", "party",
            "total_votes", "percent_of_votes", "registered_voters",
            "ballots_cast", "num_precinct_total", "num_precinct_rptg",
            "over_votes", "under_votes",
        }
        assert expected.issubset(cols)

    def test_flags_resolved_defaults_to_zero(self, db):
        db._conn.execute(
            "INSERT INTO contest_name_flags (year, contest_name_raw, contest_name) VALUES (?,?,?)",
            (2026, "Raw Name", "NORMALIZED NAME"),
        )
        db._conn.commit()
        row = db._conn.execute("SELECT resolved FROM contest_name_flags").fetchone()
        assert row[0] == 0

    def test_contest_names_primary_key(self, db):
        db.register_contest_name("FOR SENATOR", 2022)
        with pytest.raises(sqlite3.IntegrityError):
            db._conn.execute(
                "INSERT INTO contest_names (contest_name, first_seen_year) VALUES (?,?)",
                ("FOR SENATOR", 2026),
            )
            db._conn.commit()


class TestContextManager:

    def test_context_manager_closes_connection(self, tmp_path):
        db_path = tmp_path / "test.db"
        with ElectionDatabase(db_path) as db:
            assert db.query("SELECT 1") is not None
        # After exit, connection should be closed
        with pytest.raises(Exception):
            db.query("SELECT 1")


class TestGetConnection:

    def test_creates_file(self, tmp_path):
        db_path = tmp_path / "test.db"
        assert not db_path.exists()
        db = ElectionDatabase(db_path)
        db.close()
        assert db_path.exists()

    def test_default_db_path_is_path(self):
        assert isinstance(DEFAULT_DB_PATH, Path)


class TestSourceRegistry:

    def test_is_source_loaded_false_when_not_loaded(self, db):
        assert db.is_source_loaded("summary_2026.csv") is False

    def test_is_source_loaded_true_after_registering(self, db):
        db.register_source("summary_2026.csv", 2026)
        assert db.is_source_loaded("summary_2026.csv") is True

    def test_register_source_idempotent(self, db):
        db.register_source("summary_2026.csv", 2026)
        db.register_source("summary_2026.csv", 2026)  # should not raise
        sources = db.get_loaded_sources()
        assert len(sources) == 1

    def test_get_loaded_sources_returns_list_of_dicts(self, db):
        db.register_source("summary_2026.csv", 2026)
        sources = db.get_loaded_sources()
        assert isinstance(sources, list)
        assert isinstance(sources[0], dict)

    def test_get_loaded_sources_contains_filename_and_year(self, db):
        db.register_source("summary_2026.csv", 2026)
        sources = db.get_loaded_sources()
        assert sources[0]["filename"] == "summary_2026.csv"
        assert sources[0]["year"] == 2026


class TestContestNameRegistry:

    def test_get_known_returns_empty_set_initially(self, db):
        assert db.get_known_contest_names() == set()

    def test_register_and_retrieve(self, db):
        db.register_contest_name("FOR ATTORNEY GENERAL", 2022)
        assert "FOR ATTORNEY GENERAL" in db.get_known_contest_names()

    def test_register_idempotent(self, db):
        db.register_contest_name("FOR ATTORNEY GENERAL", 2022)
        db.register_contest_name("FOR ATTORNEY GENERAL", 2026)
        names = db.get_known_contest_names()
        assert list(names).count("FOR ATTORNEY GENERAL") == 1

    def test_returns_set(self, db):
        db.register_contest_name("FOR ATTORNEY GENERAL", 2022)
        assert isinstance(db.get_known_contest_names(), set)


class TestOverrides:

    def test_get_overrides_empty_initially(self, db):
        assert db.get_overrides() == {}

    def test_add_and_retrieve_override(self, db):
        db.add_override("Old Name (Vote For 1)", "FOR CANONICAL NAME")
        assert db.get_overrides() == {"Old Name (Vote For 1)": "FOR CANONICAL NAME"}

    def test_add_override_with_note(self, db):
        db.add_override("Old Name", "FOR NEW NAME", note="Renamed in 2026")
        overrides = db.get_overrides()
        assert overrides["Old Name"] == "FOR NEW NAME"

    def test_add_override_replaces_existing(self, db):
        db.add_override("Old Name", "FOR FIRST NAME")
        db.add_override("Old Name", "FOR SECOND NAME")
        assert db.get_overrides()["Old Name"] == "FOR SECOND NAME"

    def test_multiple_overrides(self, db):
        db.add_override("Raw A", "Canonical A")
        db.add_override("Raw B", "Canonical B")
        overrides = db.get_overrides()
        assert overrides["Raw A"] == "Canonical A"
        assert overrides["Raw B"] == "Canonical B"


class TestFlags:

    def test_get_unresolved_flags_empty_initially(self, db):
        assert db.get_unresolved_flags() == []

    def test_resolve_flag_marks_resolved(self, db):
        db._conn.execute(
            "INSERT INTO contest_name_flags (year, contest_name_raw, contest_name) VALUES (?,?,?)",
            (2026, "Raw", "NORMALIZED"),
        )
        db._conn.commit()
        flag_id = db._conn.execute("SELECT id FROM contest_name_flags").fetchone()[0]
        db.resolve_flag(flag_id)
        assert db.get_unresolved_flags() == []

    def test_get_unresolved_flags_returns_list_of_dicts(self, db):
        db._conn.execute(
            "INSERT INTO contest_name_flags (year, contest_name_raw, contest_name) VALUES (?,?,?)",
            (2026, "Raw", "NORMALIZED"),
        )
        db._conn.commit()
        flags = db.get_unresolved_flags()
        assert isinstance(flags, list)
        assert isinstance(flags[0], dict)

    def test_unresolved_flag_has_expected_keys(self, db):
        db._conn.execute(
            "INSERT INTO contest_name_flags (year, contest_name_raw, contest_name) VALUES (?,?,?)",
            (2026, "Raw", "NORMALIZED"),
        )
        db._conn.commit()
        flag = db.get_unresolved_flags()[0]
        assert {"id", "year", "contest_name_raw", "contest_name"}.issubset(flag.keys())
