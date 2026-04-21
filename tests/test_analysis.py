"""
Tests for dupage_elections.analysis (ElectionAnalyzer)
"""

import pytest
import pandas as pd

from dupage_elections.analysis import ElectionAnalyzer
from tests.conftest import seed_results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_with_results(db):
    """
    Database seeded with a minimal but realistic dataset:
      - ATTORNEY GENERAL: DEM + REP across all 4 years (fully comparable)
      - COUNTY CLERK: DEM missing in 2026 (not comparable for recent)
      - COMPTROLLER: DEM + REP in 2022 + 2026 only (comparable recent, not all)
    """
    seed_results(db, [
        # ATTORNEY GENERAL — comparable across all 4 years
        {"year": 2014, "contest_name": "FOR ATTORNEY GENERAL", "party": "DEM", "total_votes": 14000, "registered_voters": 576000, "ballots_cast": 110000},
        {"year": 2014, "contest_name": "FOR ATTORNEY GENERAL", "party": "REP", "total_votes": 72000, "registered_voters": 576000, "ballots_cast": 110000},
        {"year": 2018, "contest_name": "FOR ATTORNEY GENERAL", "party": "DEM", "total_votes": 81000, "registered_voters": 633000, "ballots_cast": 157000},
        {"year": 2018, "contest_name": "FOR ATTORNEY GENERAL", "party": "REP", "total_votes": 66000, "registered_voters": 633000, "ballots_cast": 157000},
        {"year": 2022, "contest_name": "FOR ATTORNEY GENERAL", "party": "DEM", "total_votes": 68000, "registered_voters": 636000, "ballots_cast": 145000},
        {"year": 2022, "contest_name": "FOR ATTORNEY GENERAL", "party": "REP", "total_votes": 63000, "registered_voters": 636000, "ballots_cast": 145000},
        {"year": 2026, "contest_name": "FOR ATTORNEY GENERAL", "party": "DEM", "total_votes": 100000, "registered_voters": 636000, "ballots_cast": 161000},
        {"year": 2026, "contest_name": "FOR ATTORNEY GENERAL", "party": "REP", "total_votes": 43000,  "registered_voters": 636000, "ballots_cast": 161000},
        # COUNTY CLERK — DEM missing in 2026, not comparable for recent
        {"year": 2022, "contest_name": "FOR COUNTY CLERK", "party": "DEM", "total_votes": 65000, "registered_voters": 636000, "ballots_cast": 145000},
        {"year": 2022, "contest_name": "FOR COUNTY CLERK", "party": "REP", "total_votes": 59000, "registered_voters": 636000, "ballots_cast": 145000},
        {"year": 2026, "contest_name": "FOR COUNTY CLERK", "party": "REP", "total_votes": 41000,  "registered_voters": 636000, "ballots_cast": 161000},
        # COMPTROLLER — comparable recent (2022+2026), but not all 4 years
        {"year": 2022, "contest_name": "FOR COMPTROLLER", "party": "DEM", "total_votes": 68000, "registered_voters": 636000, "ballots_cast": 145000},
        {"year": 2022, "contest_name": "FOR COMPTROLLER", "party": "REP", "total_votes": 59000, "registered_voters": 636000, "ballots_cast": 145000},
        {"year": 2026, "contest_name": "FOR COMPTROLLER", "party": "DEM", "total_votes": 102000, "registered_voters": 636000, "ballots_cast": 161000},
        {"year": 2026, "contest_name": "FOR COMPTROLLER", "party": "REP", "total_votes": 42000,  "registered_voters": 636000, "ballots_cast": 161000},
    ])
    return db


@pytest.fixture
def analyzer(db_with_results):
    return ElectionAnalyzer(db_with_results)


# ---------------------------------------------------------------------------
# get_party_year_totals
# ---------------------------------------------------------------------------

class TestGetPartyYearTotals:

    def test_returns_dataframe(self, analyzer):
        result = analyzer.get_party_year_totals()
        assert isinstance(result, pd.DataFrame)

    def test_columns(self, analyzer):
        result = analyzer.get_party_year_totals()
        assert set(result.columns) == {"contest_name", "party", "year", "party_year_total"}

    def test_sums_votes_across_candidates(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 3000, "choice_name": "Candidate A"},
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 4000, "choice_name": "Candidate B"},
        ])
        analyzer = ElectionAnalyzer(db)
        result = analyzer.get_party_year_totals(years=[2022])
        row = result[
            (result["contest_name"] == "FOR SENATOR") &
            (result["party"] == "DEM") &
            (result["year"] == 2022)
        ]
        assert row["party_year_total"].iloc[0] == 7000

    def test_filters_by_year(self, analyzer):
        result = analyzer.get_party_year_totals(years=[2022])
        assert set(result["year"].unique()) == {2022}

    def test_filters_by_multiple_years(self, analyzer):
        result = analyzer.get_party_year_totals(years=[2022, 2026])
        assert set(result["year"].unique()) == {2022, 2026}

    def test_filters_by_party(self, analyzer):
        result = analyzer.get_party_year_totals(parties=("DEM",))
        assert set(result["party"].unique()) == {"DEM"}

    def test_no_year_filter_returns_all_years(self, analyzer):
        result = analyzer.get_party_year_totals()
        assert {2014, 2018, 2022, 2026}.issubset(set(result["year"].unique()))

    def test_one_row_per_contest_party_year(self, analyzer):
        result = analyzer.get_party_year_totals()
        dupes = result.duplicated(subset=["contest_name", "party", "year"])
        assert not dupes.any()


# ---------------------------------------------------------------------------
# get_comparable_contests
# ---------------------------------------------------------------------------

class TestGetComparableContests:

    def test_returns_set(self, analyzer):
        totals = analyzer.get_party_year_totals()
        result = analyzer.get_comparable_contests(totals, [2022, 2026])
        assert isinstance(result, set)

    def test_includes_fully_comparable_contest(self, analyzer):
        totals = analyzer.get_party_year_totals()
        result = analyzer.get_comparable_contests(totals, [2022, 2026])
        assert "FOR ATTORNEY GENERAL" in result

    def test_excludes_contest_missing_a_party(self, analyzer):
        totals = analyzer.get_party_year_totals()
        result = analyzer.get_comparable_contests(totals, [2022, 2026])
        assert "FOR COUNTY CLERK" not in result

    def test_all_years_requirement(self, analyzer):
        totals = analyzer.get_party_year_totals()
        result = analyzer.get_comparable_contests(totals, [2014, 2018, 2022, 2026])
        assert "FOR ATTORNEY GENERAL" in result
        assert "FOR COMPTROLLER" not in result

    def test_excludes_contest_with_zero_votes(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 5000},
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 0},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 6000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 4000},
        ])
        analyzer = ElectionAnalyzer(db)
        totals = analyzer.get_party_year_totals()
        result = analyzer.get_comparable_contests(totals, [2022, 2026])
        assert "FOR SENATOR" not in result

    def test_empty_db_returns_empty_set(self, db):
        analyzer = ElectionAnalyzer(db)
        totals = analyzer.get_party_year_totals()
        result = analyzer.get_comparable_contests(totals, [2022, 2026])
        assert result == set()


# ---------------------------------------------------------------------------
# build_vote_totals_pivot
# ---------------------------------------------------------------------------

class TestBuildVoteTotalsPivot:

    @pytest.fixture
    def totals(self, analyzer):
        return analyzer.get_party_year_totals()

    @pytest.fixture
    def comparable(self, analyzer, totals):
        return analyzer.get_comparable_contests(totals, [2022, 2026])

    def test_returns_dataframe(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        assert isinstance(result, pd.DataFrame)

    def test_has_contest_column(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        assert "contest" in result.columns

    def test_has_year_columns_for_each_party(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        for col in ["DEM 2022", "DEM 2026", "REP 2022", "REP 2026"]:
            assert col in result.columns

    def test_has_pct_change_columns(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        assert "DEM Votes 26 vs 22" in result.columns
        assert "REP Votes 26 vs 22" in result.columns

    def test_pct_change_calculation(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        row = result[result["contest"] == "FOR ATTORNEY GENERAL"].iloc[0]
        expected = (100000 - 68000) / 68000
        assert abs(row["DEM Votes 26 vs 22"] - expected) < 1e-6

    def test_only_includes_comparable_contests(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        assert "FOR COUNTY CLERK" not in result["contest"].values

    def test_column_order_dem_before_rep(self, analyzer, totals, comparable):
        result = analyzer.build_vote_totals_pivot(totals, comparable, [2022, 2026], 2022, 2026)
        cols = list(result.columns)
        dem_idx = next(i for i, c in enumerate(cols) if c.startswith("DEM"))
        rep_idx = next(i for i, c in enumerate(cols) if c.startswith("REP"))
        assert dem_idx < rep_idx

    def test_four_year_comparison(self, analyzer, totals):
        comparable_all = analyzer.get_comparable_contests(totals, [2014, 2018, 2022, 2026])
        result = analyzer.build_vote_totals_pivot(
            totals, comparable_all, [2014, 2018, 2022, 2026], 2014, 2026
        )
        assert "DEM 2014" in result.columns
        assert "DEM 2018" in result.columns
        assert "DEM Votes 26 vs 14" in result.columns


# ---------------------------------------------------------------------------
# build_party_share_pivot
# ---------------------------------------------------------------------------

class TestBuildPartySharePivot:

    @pytest.fixture
    def comparable_recent(self, analyzer):
        totals = analyzer.get_party_year_totals()
        return analyzer.get_comparable_contests(totals, [2022, 2026])

    def test_returns_dataframe(self, analyzer, comparable_recent):
        result = analyzer.build_party_share_pivot(comparable_recent, [2022, 2026], 2022, 2026)
        assert isinstance(result, pd.DataFrame)

    def test_has_share_columns(self, analyzer, comparable_recent):
        result = analyzer.build_party_share_pivot(comparable_recent, [2022, 2026], 2022, 2026)
        for col in ["DEM % of Total 2022", "DEM % of Total 2026", "REP % of Total 2022", "REP % of Total 2026"]:
            assert col in result.columns

    def test_has_change_columns(self, analyzer, comparable_recent):
        result = analyzer.build_party_share_pivot(comparable_recent, [2022, 2026], 2022, 2026)
        assert "DEM % of Total 26 vs 22" in result.columns
        assert "REP % of Total 26 vs 22" in result.columns

    def test_share_sums_to_one_when_only_two_parties(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 6000},
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 4000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 7000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 3000},
        ])
        analyzer = ElectionAnalyzer(db)
        totals = analyzer.get_party_year_totals()
        comparable = analyzer.get_comparable_contests(totals, [2022, 2026])
        result = analyzer.build_party_share_pivot(comparable, [2022, 2026], 2022, 2026)
        row = result[result["contest"] == "FOR SENATOR"].iloc[0]
        assert abs(row["DEM % of Total 2022"] + row["REP % of Total 2022"] - 1.0) < 1e-6
        assert abs(row["DEM % of Total 2026"] + row["REP % of Total 2026"] - 1.0) < 1e-6

    def test_share_calculation(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 6000},
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 4000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 7000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 3000},
        ])
        analyzer = ElectionAnalyzer(db)
        totals = analyzer.get_party_year_totals()
        comparable = analyzer.get_comparable_contests(totals, [2022, 2026])
        result = analyzer.build_party_share_pivot(comparable, [2022, 2026], 2022, 2026)
        row = result[result["contest"] == "FOR SENATOR"].iloc[0]
        assert abs(row["DEM % of Total 2022"] - 0.6) < 1e-6
        assert abs(row["REP % of Total 2022"] - 0.4) < 1e-6

    def test_change_in_percentage_points(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 5000},
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 5000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "DEM", "total_votes": 6000},
            {"year": 2026, "contest_name": "FOR SENATOR", "party": "REP", "total_votes": 4000},
        ])
        analyzer = ElectionAnalyzer(db)
        totals = analyzer.get_party_year_totals()
        comparable = analyzer.get_comparable_contests(totals, [2022, 2026])
        result = analyzer.build_party_share_pivot(comparable, [2022, 2026], 2022, 2026)
        row = result[result["contest"] == "FOR SENATOR"].iloc[0]
        assert abs(row["DEM % of Total 26 vs 22"] - 10.0) < 1e-6
        assert abs(row["REP % of Total 26 vs 22"] - (-10.0)) < 1e-6

    def test_only_includes_comparable_contests(self, analyzer, comparable_recent):
        result = analyzer.build_party_share_pivot(comparable_recent, [2022, 2026], 2022, 2026)
        assert "FOR COUNTY CLERK" not in result["contest"].values


# ---------------------------------------------------------------------------
# build_turnout
# ---------------------------------------------------------------------------

class TestBuildTurnout:

    def test_returns_dataframe(self, analyzer):
        result = analyzer.build_turnout()
        assert isinstance(result, pd.DataFrame)

    def test_index_labels(self, analyzer):
        result = analyzer.build_turnout()
        assert list(result.index) == ["% Vote", "Registered", "Ballots Cast"]

    def test_columns_are_years(self, analyzer):
        result = analyzer.build_turnout()
        assert 2022 in result.columns
        assert 2026 in result.columns

    def test_pct_vote_calculation(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM",
             "total_votes": 5000, "registered_voters": 100000, "ballots_cast": 25000},
        ])
        analyzer = ElectionAnalyzer(db)
        result = analyzer.build_turnout()
        assert abs(result.loc["% Vote", 2022] - 0.25) < 1e-6

    def test_uses_max_registered_voters_per_year(self, db):
        seed_results(db, [
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM",
             "total_votes": 5000, "registered_voters": 636000, "ballots_cast": 145000},
            {"year": 2022, "contest_name": "FOR LOCAL RACE", "party": "DEM",
             "total_votes": 1000, "registered_voters": 10000, "ballots_cast": 5000},
        ])
        analyzer = ElectionAnalyzer(db)
        result = analyzer.build_turnout()
        assert result.loc["Registered", 2022] == 636000

    def test_years_are_columns(self, db):
        seed_results(db, [
            {"year": 2018, "contest_name": "FOR SENATOR", "party": "DEM",
             "total_votes": 5000, "registered_voters": 633000, "ballots_cast": 157000},
            {"year": 2022, "contest_name": "FOR SENATOR", "party": "DEM",
             "total_votes": 5000, "registered_voters": 636000, "ballots_cast": 145000},
        ])
        analyzer = ElectionAnalyzer(db)
        result = analyzer.build_turnout()
        assert 2018 in result.columns
        assert 2022 in result.columns

    def test_index_name_is_metric(self, analyzer):
        result = analyzer.build_turnout()
        assert result.index.name == "Metric"
