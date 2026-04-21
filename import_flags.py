"""
import_flags.py
---------------
Read a reviewed flags spreadsheet and update the database accordingly.

Processes rows where Status is set to:
  accepted   Register the Normalized Suggestion as a known contest name
             and mark the flag resolved.
  mapped     Add an override mapping Raw Name -> Override Target,
             register the target as a known contest name, and mark resolved.
  ignored    Mark the flag resolved without registering anything.
  unreviewed Skip (no changes made).

Usage:
    python import_flags.py [flags_review.xlsx]
"""

import sys
from pathlib import Path

import pandas as pd

from dupage_elections.db import ElectionDatabase, DEFAULT_DB_PATH

DEFAULT_INPUT = Path("flags_review.xlsx")

VALID_STATUSES = {"accepted", "mapped", "ignored", "unreviewed"}


def import_flags(
    input_path: Path = DEFAULT_INPUT,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    df = pd.read_excel(input_path, sheet_name="flags", dtype=str)
    df = df.fillna("")
    df.columns = [c.strip() for c in df.columns]

    # Validate required columns
    required = {"Flag ID", "Year", "Raw Name", "Normalized Suggestion", "Status"}
    missing = required - set(df.columns)
    if missing:
        print(f"Missing columns in spreadsheet: {missing}")
        sys.exit(1)

    # Normalize status values for comparison
    df["Status"] = df["Status"].str.strip().str.lower()

    invalid = set(df["Status"].unique()) - VALID_STATUSES
    if invalid:
        print(f"Warning: unrecognized Status values will be skipped: {invalid}")

    counts = {"accepted": 0, "mapped": 0, "ignored": 0, "skipped": 0, "errors": 0}

    with ElectionDatabase(db_path) as db:
        for _, row in df.iterrows():
            known = db.get_known_contest_names()  # refresh each row
            status = row["Status"]
            flag_id = int(row["Flag ID"])
            year = int(row["Year"])
            raw_name = row["Raw Name"].strip()
            normalized = row["Normalized Suggestion"].strip()
            override_target = row.get("Override Target", "").strip()

            if status == "unreviewed":
                counts["skipped"] += 1
                continue

            elif status == "accepted":
                db.register_contest_name(normalized, year)
                db.resolve_flag(flag_id)
                counts["accepted"] += 1

            elif status == "mapped":
                if not override_target:
                    print(f"  ✗ Flag {flag_id} ({raw_name!r}): Status is 'mapped' but Override Target is empty — skipped.")
                    counts["errors"] += 1
                    continue
                if override_target not in known:
                    print(f"  ✗ Flag {flag_id} ({raw_name!r}): Override Target {override_target!r} not found in known contest names — skipped.")
                    counts["errors"] += 1
                    continue
                db.add_override(raw_name, override_target)
                db.register_contest_name(override_target, year)
                db.resolve_flag(flag_id)
                counts["mapped"] += 1

            elif status == "ignored":
                db.resolve_flag(flag_id)
                counts["ignored"] += 1

    print(f"Import complete:")
    print(f"  {counts['accepted']:>5} accepted")
    print(f"  {counts['mapped']:>5} mapped")
    print(f"  {counts['ignored']:>5} ignored")
    print(f"  {counts['skipped']:>5} unreviewed (skipped)")
    if counts["errors"]:
        print(f"  {counts['errors']:>5} errors — fix and re-run")

    remaining = counts["skipped"] + counts["errors"]
    if remaining:
        print(f"\n{remaining} flag(s) still unresolved. Re-export and review to continue.")


if __name__ == "__main__":
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB_PATH
    import_flags(input_path=input_path, db_path=db_path)
