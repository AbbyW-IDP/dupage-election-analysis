"""
review_flags.py
---------------
Interactive CLI for resolving flagged contest names after syncing new sources.

For each unresolved flag, you can:
  [a] Accept as a new contest (adds to contest_names, marks flag resolved)
  [m] Map to an existing contest name (adds to contest_name_overrides)
  [s] Skip for now

Usage:
    python review_flags.py
"""

import sys
from pathlib import Path

from dupage_elections.db import ElectionDatabase, DEFAULT_DB_PATH


def main(db_path: Path = DEFAULT_DB_PATH) -> None:
    with ElectionDatabase(db_path) as db:
        flags = db.get_unresolved_flags()

        if not flags:
            print("No unresolved contest name flags.")
            return

        print(f"{len(flags)} unresolved flag(s).\n")

        for flag in flags:
            flag_id  = flag["id"]
            year     = flag["year"]
            raw_name = flag["contest_name_raw"]
            norm     = flag["contest_name"]

            print(f"Year:       {year}")
            print(f"Raw name:   {raw_name}")
            print(f"Normalized: {norm}")
            print()
            print("  [a] Accept as new contest")
            print("  [m] Map to an existing contest name")
            print("  [s] Skip")
            print()

            while True:
                choice = input("Choice: ").strip().lower()

                if choice == "a":
                    db.register_contest_name(norm, year)
                    db.resolve_flag(flag_id)
                    print("  ✓ Accepted.\n")
                    break

                elif choice == "m":
                    known = sorted(db.get_known_contest_names())
                    query = input("  Search existing names (or Enter to list all): ").strip().lower()
                    matches = [n for n in known if query in n.lower()] if query else known
                    if not matches:
                        print("  No matches found.")
                        continue
                    for i, name in enumerate(matches[:20], 1):
                        print(f"  {i:>2}. {name}")
                    if len(matches) > 20:
                        print(f"  ... and {len(matches) - 20} more. Refine your search.")
                        continue
                    idx = input("  Enter number to select: ").strip()
                    if not idx.isdigit() or not (1 <= int(idx) <= len(matches)):
                        print("  Invalid selection.")
                        continue
                    canonical = matches[int(idx) - 1]
                    note = input(f"  Note (optional, e.g. 'Renamed in {year}'): ").strip()
                    db.add_override(raw_name, canonical, note or None)
                    db.resolve_flag(flag_id)
                    print(f"  ✓ Mapped to: {canonical}\n")
                    break

                elif choice == "s":
                    print("  Skipped.\n")
                    break

                else:
                    print("  Please enter a, m, or s.")

        remaining = len(db.get_unresolved_flags())
        if remaining:
            print(f"{remaining} flag(s) still unresolved. Run again to continue.")
        else:
            print("All flags resolved.")


if __name__ == "__main__":
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    main(db_path)
