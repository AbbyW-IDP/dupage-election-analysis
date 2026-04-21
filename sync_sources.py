"""
sync_sources.py
---------------
Scan the sources/ directory for new CSV files and load them into the database.
Files already in the database are skipped. Database entries are never removed
when a source file is deleted.

CSV filenames must contain a 4-digit year, e.g. summary_2026.csv.

Usage:
    python sync_sources.py [sources_dir] [db_path]
"""

import sys
from pathlib import Path

from dupage_elections.db import ElectionDatabase, DEFAULT_DB_PATH
from dupage_elections.loader import ElectionLoader

DEFAULT_SOURCES_DIR = Path("sources")


def main(
    sources_dir: Path = DEFAULT_SOURCES_DIR,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    with ElectionDatabase(db_path) as db:
        loader = ElectionLoader(db)

        print(f"Scanning {sources_dir} for new election files...")
        results = loader.sync_sources(sources_dir)

        if not results:
            print("No new files found.")
            return

        any_flags = False
        for filename, (inserted, new_names) in results.items():
            print(f"\n  {filename}: inserted {inserted:,} rows")
            if new_names:
                any_flags = True
                print(f"  ⚠  {len(new_names)} unrecognized contest name(s):")
                for name in new_names:
                    print(f"    {name}")

        if any_flags:
            print("\nRun: python review_flags.py")
        else:
            print("\nAll contest names matched known contests.")


if __name__ == "__main__":
    sources_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCES_DIR
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB_PATH
    main(sources_dir, db_path)
