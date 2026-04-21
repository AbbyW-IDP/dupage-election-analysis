"""
analysis.py
-----------
ElectionAnalyzer: produces analysis DataFrames from an ElectionDatabase.
Each method corresponds to one output tab.
"""

import pandas as pd

from dupage_elections.db import ElectionDatabase


class ElectionAnalyzer:
    """
    Produces analysis DataFrames from an ElectionDatabase.

    Args:
        db: An ElectionDatabase instance to read from.

    Usage:
        analyzer = ElectionAnalyzer(db)
        totals = analyzer.get_party_year_totals()
        comparable = analyzer.get_comparable_contests(totals, [2022, 2026])
        pivot = analyzer.build_vote_totals_pivot(totals, comparable, ...)
    """

    def __init__(self, db: ElectionDatabase) -> None:
        self._db = db

    def get_party_year_totals(
        self,
        years: list[int] | None = None,
        parties: tuple[str, ...] = ("DEM", "REP"),
    ) -> pd.DataFrame:
        """
        Aggregate total votes per contest × party × year.
        The building block for all other analysis methods.
        """
        query = "SELECT year, contest_name, party, total_votes FROM results WHERE 1=1"
        params: list = []

        if years:
            query += f" AND year IN ({','.join('?' * len(years))})"
            params.extend(years)
        if parties:
            query += f" AND party IN ({','.join('?' * len(parties))})"
            params.extend(parties)

        df = self._db.query(query, params)
        return (
            df.groupby(["contest_name", "party", "year"])["total_votes"]
            .sum()
            .reset_index()
            .rename(columns={"total_votes": "party_year_total"})
        )

    def get_comparable_contests(
        self,
        totals: pd.DataFrame,
        required_years: list[int],
        required_parties: tuple[str, ...] = ("DEM", "REP"),
    ) -> set[str]:
        """
        Return contest names where every combination of required_years ×
        required_parties has votes > 0.
        """
        required_combos = len(required_years) * len(required_parties)
        valid = (
            totals[
                totals["year"].isin(required_years)
                & totals["party"].isin(required_parties)
                & (totals["party_year_total"] > 0)
            ]
            .groupby("contest_name")
            .filter(lambda g: len(g) == required_combos)["contest_name"]
            .unique()
        )
        return set(valid)

    def build_vote_totals_pivot(
        self,
        totals: pd.DataFrame,
        comparable_contests: set[str],
        years: list[int],
        base_year: int,
        compare_year: int,
    ) -> pd.DataFrame:
        """
        Wide table of vote totals per party per year, plus % change between
        base_year and compare_year.

        Columns: contest, DEM <year>..., DEM Votes <cmp> vs <base>, REP ...
        """
        df = totals[
            totals["contest_name"].isin(comparable_contests)
            & totals["year"].isin(years)
        ].copy()

        pivot = df.pivot_table(
            index="contest_name", columns=["party", "year"], values="party_year_total"
        )
        pivot.columns = [f"{p} {y}" for p, y in pivot.columns]
        pivot = pivot.reset_index()

        suffix = f"{str(compare_year)[-2:]} vs {str(base_year)[-2:]}"
        for party in ("DEM", "REP"):
            col_base = f"{party} {base_year}"
            col_cmp = f"{party} {compare_year}"
            pivot[f"{party} Votes {suffix}"] = (pivot[col_cmp] - pivot[col_base]) / pivot[col_base]

        ordered = ["contest_name"]
        for party in ("DEM", "REP"):
            ordered += [f"{party} {y}" for y in years]
            ordered += [f"{party} Votes {suffix}"]

        return pivot[ordered].rename(columns={"contest_name": "contest"})

    def build_party_share_pivot(
        self,
        comparable_contests: set[str],
        years: list[int],
        base_year: int,
        compare_year: int,
        parties: tuple[str, ...] = ("DEM", "REP"),
    ) -> pd.DataFrame:
        """
        Wide table of each party's share of total contest votes per year,
        plus percentage-point change between base_year and compare_year.

        The denominator is all votes cast in the contest/year across all parties.
        """
        all_votes = self._db.query(
            f"""
            SELECT year, contest_name, SUM(total_votes) AS contest_year_total
            FROM results
            WHERE year IN ({','.join('?' * len(years))})
            GROUP BY year, contest_name
            """,
            years,
        )

        totals = self.get_party_year_totals(years=years, parties=list(parties))
        totals = totals[totals["contest_name"].isin(comparable_contests)]
        totals = totals.merge(all_votes, on=["contest_name", "year"])
        totals["vote_share"] = totals["party_year_total"] / totals["contest_year_total"]

        pivot = totals.pivot_table(
            index="contest_name", columns=["party", "year"], values="vote_share"
        )
        pivot.columns = [f"{p} % of Total {y}" for p, y in pivot.columns]
        pivot = pivot.reset_index()

        suffix = f"{str(compare_year)[-2:]} vs {str(base_year)[-2:]}"
        for party in parties:
            col_base = f"{party} % of Total {base_year}"
            col_cmp = f"{party} % of Total {compare_year}"
            pivot[f"{party} % of Total {suffix}"] = (pivot[col_cmp] - pivot[col_base]) * 100

        ordered = ["contest_name"]
        for party in parties:
            ordered += [
                f"{party} % of Total {base_year}",
                f"{party} % of Total {compare_year}",
                f"{party} % of Total {suffix}",
            ]

        return pivot[ordered].rename(columns={"contest_name": "contest"})

    def build_turnout(self) -> pd.DataFrame:
        """
        Registered voters, ballots cast, and turnout rate by year.
        """
        df = self._db.query("""
            SELECT year,
                   MAX(registered_voters) AS registered_voters,
                   MAX(ballots_cast)      AS ballots_cast
            FROM results
            GROUP BY year
            ORDER BY year
        """)
        df["pct_vote"] = df["ballots_cast"] / df["registered_voters"]
        result = df.set_index("year")[["pct_vote", "registered_voters", "ballots_cast"]].T
        result.index = ["% Vote", "Registered", "Ballots Cast"]
        result.index.name = "Metric"
        return result
