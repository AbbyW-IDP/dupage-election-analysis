# DuPage County Election Analysis

Analysis of partisan primary election results in DuPage County, Illinois across multiple election cycles (2014, 2018, 2022, 2026).

Data are sourced from [DuPage County Election Results](https://www.dupageresults.gov/IL/DuPage/) and cover candidate-level vote totals by contest, party, and year.

---

## Repository structure

```
.
├── README.md
├── pyproject.toml
├── setup_db.py              # One-time setup: load historical Excel workbook
├── sync_sources.py          # Load new CSVs from the sources/ directory
├── generate_analysis.py     # Produce Excel output from the database
├── export_flags.py          # Export unresolved flags to a spreadsheet for review
├── import_flags.py          # Import reviewed flags spreadsheet and update the database
├── review_flags.py          # Interactive CLI for resolving flags one at a time
├── sources/                 # Drop election CSVs here to load them
│   ├── 2022-general-primary-2022-07-19.csv
│   └── 2026-general-primary-2026-04-07.csv
├── dupage_elections/
│   ├── db.py                # ElectionDatabase class
│   ├── loader.py            # ElectionLoader class
│   ├── analysis.py          # ElectionAnalyzer class
│   └── normalize.py         # Contest name and party normalization functions
└── tests/
    ├── conftest.py
    ├── test_db.py
    ├── test_loader.py
    ├── test_analysis.py
    └── test_normalize.py
```

> `elections.db` is generated locally by running `setup_db.py` and is not committed to the repository.

---

## Getting started

### Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) for dependency management

### Install

```bash
uv sync
```

### First-time setup

Run `setup_db.py` once to create `elections.db` from the historical Excel workbook. It will also sync any CSVs already in `sources/`:

```bash
uv run python setup_db.py
```

By default it looks for `comparison_14-26_official.xlsx` in the current directory. You can pass a custom path:

```bash
uv run python setup_db.py path/to/workbook.xlsx
```

---

## Adding new elections

Place the raw CSV for the new election in the `sources/` directory. The filename must contain a 4-digit year — the year at the start of the filename is used as the election year, so date-suffixed names like `2030-general-primary-2030-07-15.csv` work correctly. Then run:

```bash
uv run python sync_sources.py
```

`sync_sources.py` scans `sources/` for any CSV files not yet in the database and loads them. Files already loaded are skipped. **Database entries are never removed**, even if the source file is later deleted — this preserves historical data regardless of what's on disk.

If any contest names in the new file don't match known names, they are flagged for review. See [Reviewing flagged contest names](#reviewing-flagged-contest-names) below.

---

## Generating analysis output

```bash
uv run python generate_analysis.py
```

This writes `election_analysis.xlsx` with the following sheets:

| Sheet | Description |
|---|---|
| `turnout` | Registered voters, ballots cast, and turnout rate by year |
| `22-26 pct change by party` | Vote totals per party per contest, 2022 vs. 2026 |
| `22-26 party share` | Each party's share of total contest votes, 2022 vs. 2026 |
| `22-26 comparison` | Vote totals and party share combined |
| `14-26 pct change by party` | Vote totals per party per contest across all four years |

All analysis is filtered to **comparable contests** — contests where both DEM and REP had votes in every year being compared.

---

## Contest name normalization

Raw contest names vary across years. The following transformations are applied automatically when loading any source file:

| Rule | Example input | Normalized output |
|---|---|---|
| Uppercase | `United States Senator` | `UNITED STATES SENATOR` |
| Strip party suffixes | `FOR SENATOR - D*` | `FOR SENATOR` |
| Strip parentheticals | `FOR SENATOR (Vote For 1)` | `FOR SENATOR` |
| Strip term-length suffixes | `District 1, 4 Year Term - R` | `DISTRICT 1` |
| Gender-neutral titles | `FOR PRECINCT COMMITTEEWOMAN YORK 050` | `FOR PRECINCT COMMITTEEPERSON YORK 050` |
| Spell out ordinals | `81ST REPRESENTATIVE DISTRICT` | `EIGHTY-FIRST REPRESENTATIVE DISTRICT` |

Plain integers (e.g. `District 1`) are preserved. Only ordinal suffixes like `1st`, `21st`, `81st` are expanded. Original raw contest names are always stored alongside normalized names for reference.

---

## Reviewing flagged contest names

After loading a new election, any normalized contest name that doesn't match the registry is flagged. There are two ways to resolve flags.

### Option A — Spreadsheet review (recommended for large batches)

Export all unresolved flags to a spreadsheet:

```bash
uv run python export_flags.py
```

This writes `flags_review.xlsx` with two tabs:

- **`flags`** — one row per unresolved flag, with columns: Flag ID, Year, Raw Name, Normalized Suggestion, Status, Override Target, Notes
- **`known_contests`** — all normalized contest names currently in the registry, for reference when mapping

Open the spreadsheet and set the **Status** column for each row:

| Status | Meaning |
|---|---|
| `unreviewed` | Default. Row will be skipped on import. |
| `accepted` | Accept the Normalized Suggestion as a new contest name. |
| `mapped` | Map to an existing contest. Fill in **Override Target** with the exact name from the `known_contests` tab. |
| `ignored` | Acknowledge the flag without registering anything (e.g. ballot measures you don't want to track). |

You can work through flags in batches — `unreviewed` rows are always skipped on import, so you can import partially and re-export to continue. Once you've reviewed your rows, import the results:

```bash
uv run python import_flags.py
```

The script reports how many flags were accepted, mapped, ignored, and skipped, and tells you how many remain unresolved.

### Option B — Interactive terminal review

For smaller batches, resolve flags one at a time in the terminal:

```bash
uv run python review_flags.py
```

For each flag you can accept it as a new contest, map it to an existing one, or skip it for later.

### How overrides work

When a flag is marked `mapped`, an entry is added to the `contest_name_overrides` table linking the raw name to the canonical normalized name. On all future loads, any raw contest name with an override is mapped directly without going through normalization — so if a county renames a contest but it's the same race, you can map it once and it will be handled correctly forever after.

---

## Architecture

The project uses three main classes:

**`ElectionDatabase`** (`db.py`) owns all database state: the SQLite connection, schema, contest name registry, flags, overrides, and source file registry. All other classes interact with the database through this interface.

**`ElectionLoader`** (`loader.py`) reads source files and loads them into an `ElectionDatabase`. Supports CSV files and the historical Excel workbook. The `sync_sources()` method scans a directory and loads only files not already registered.

**`ElectionAnalyzer`** (`analysis.py`) reads from an `ElectionDatabase` and produces analysis DataFrames. Each method corresponds to one output tab.

`normalize.py` contains pure functions for contest name and party normalization — no state, no I/O, fully unit-tested independently.

---

## Database schema

**`results`** — one row per candidate per contest per year

| Column | Description |
|---|---|
| `year` | Election year |
| `source_file` | Filename the row was loaded from |
| `contest_name_raw` | Original contest name from the source file |
| `contest_name` | Normalized contest name |
| `choice_name` | Candidate name |
| `party` | Party (`DEM`, `REP`, `GP`, `WC`, etc.) |
| `total_votes` | Votes received by this candidate |
| `percent_of_votes` | Candidate's share within their party primary |
| `registered_voters` | Registered voters in the contest |
| `ballots_cast` | Ballots cast in the contest |

**`contest_names`** — registry of known normalized contest names

**`contest_name_flags`** — names from new sources that didn't match any known name

**`contest_name_overrides`** — manual mappings from a raw name to a canonical normalized name

**`loaded_sources`** — registry of source files that have been loaded into the database

---

## Running tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=dupage_elections --cov-report=term-missing
```

In parallel:

```bash
uv run pytest -n auto
```

---

## Data notes

- Results cover DuPage County primary elections only
- Only DEM and REP contests are used in partisan comparisons; other parties are stored but excluded from analysis
- 2026 results are official as of April 7, 2026
- Turnout figures use the maximum registered voter and ballots cast values across all contests in a given year, which represent the county-wide figures
