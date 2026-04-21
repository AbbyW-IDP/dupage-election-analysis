"""
setup_db.py
-----------
One-time setup: loads the historical Excel workbook into elections.db,
then syncs any CSVs already present in the sources/ directory.

Usage:
    python setup_db.py [path/to/workbook.xlsx] [sources_dir]
"""

import sys
from pathlib import Path

from dupage_elections.db import ElectionDatabase, DEFAULT_DB_PATH
from dupage_elections.loader import ElectionLoader

DEFAULT_EXCEL  = Path("comparison_14-26_official.xlsx")
DEFAULT_SOURCES = Path("sources")


def main(
    excel_path: Path = DEFAULT_EXCEL,
    sources_dir: Path = DEFAULT_SOURCES,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    with ElectionDatabase(db_path) as db:
        loader = ElectionLoader(db)

        print(f"Loading {excel_path}...")
        year_results = loader.load_excel(excel_path)
        for year, (inserted, new_names) in sorted(year_results.items()):
            print(f"  {year}: {inserted:,} rows")
            if new_names:
                print(f"    ⚠  {len(new_names)} new contest name(s) registered")

        if sources_dir.exists():
            print(f"\nSyncing {sources_dir}...")
            sync_results = loader.sync_sources(sources_dir)
            if sync_results:
                for filename, (inserted, new_names) in sync_results.items():
                    print(f"  {filename}: {inserted:,} rows")
                    if new_names:
                        print(f"    ⚠  {len(new_names)} unrecognized contest name(s)")
            else:
                print("  No new CSV files found.")

    print(f"\nDone. Run sync_sources.py to load future election CSVs.")


if __name__ == "__main__":
    excel_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXCEL
    sources_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SOURCES
    main(excel_path, sources_dir)
