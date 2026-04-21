"""
generate_analysis.py
--------------------
Produce all analysis outputs and write them to an Excel workbook.

Usage:
    python generate_analysis.py [output.xlsx]
"""

import sys
from pathlib import Path

import pandas as pd

from dupage_elections.db import ElectionDatabase, DEFAULT_DB_PATH
from dupage_elections.analysis import ElectionAnalyzer

DEFAULT_OUTPUT = Path("election_analysis.xlsx")


def main(
    output_path: Path = DEFAULT_OUTPUT,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    with ElectionDatabase(db_path) as db:
        analyzer = ElectionAnalyzer(db)

        totals = analyzer.get_party_year_totals()
        comparable_all    = analyzer.get_comparable_contests(totals, [2014, 2018, 2022, 2026])
        comparable_recent = analyzer.get_comparable_contests(totals, [2022, 2026])

        print(f"Comparable across all 4 years: {len(comparable_all)} contests")
        print(f"Comparable across 2022 & 2026: {len(comparable_recent)} contests")

        turnout = analyzer.build_turnout()

        pct_change_22_26 = analyzer.build_vote_totals_pivot(
            totals, comparable_recent,
            years=[2022, 2026], base_year=2022, compare_year=2026,
        )
        party_share_22_26 = analyzer.build_party_share_pivot(
            comparable_recent,
            years=[2022, 2026], base_year=2022, compare_year=2026,
        )
        comparison_22_26 = pct_change_22_26.merge(party_share_22_26, on="contest")

        pct_change_14_26 = analyzer.build_vote_totals_pivot(
            totals, comparable_all,
            years=[2014, 2018, 2022, 2026], base_year=2014, compare_year=2026,
        )

        print(f"\nWriting to {output_path}...")
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            turnout.to_excel(writer, sheet_name="turnout")
            pct_change_22_26.to_excel(writer, sheet_name="22-26 pct change by party", index=False)
            party_share_22_26.to_excel(writer, sheet_name="22-26 party share", index=False)
            comparison_22_26.to_excel(writer, sheet_name="22-26 comparison", index=False)
            pct_change_14_26.to_excel(writer, sheet_name="14-26 pct change by party", index=False)

    print("Done.")


if __name__ == "__main__":
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    main(output_path)
