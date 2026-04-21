"""
load_election.py
----------------
Load a new election CSV into the database.

Usage:
    python load_election.py data/summary_2030.csv 2030

Unrecognized contest names are flagged for review. After loading, run:
    python review_flags.py
"""

import sys
from pathlib import Path

from dupage_elections.db import get_connection, DEFAULT_DB_PATH
from dupage_elections.loader import read_csv, insert_results


def main(csv_path: Path, year: int, db_path: Path = DEFAULT_DB_PATH) -> None:
    print(f"Loading {csv_path} (year={year}) into {db_path}...")
    conn = get_connection(db_path)

    df = read_csv(csv_path)
    inserted, new_names = insert_results(conn, df, year)
    conn.close()

    print(f"  Inserted {inserted:,} rows.")

    if new_names:
        print(f"\n  ⚠  {len(new_names)} unrecognized contest name(s) flagged for review:")
        for name in new_names:
            print(f"    {name}")
        print("\n  Run: python review_flags.py")
    else:
        print("  ✓ All contest names matched known contests.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python load_election.py <csv_path> <year>")
        sys.exit(1)
    main(Path(sys.argv[1]), int(sys.argv[2]))
