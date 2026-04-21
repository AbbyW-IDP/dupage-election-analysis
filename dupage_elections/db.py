"""
db.py
-----
ElectionDatabase: wraps the SQLite connection and owns all database operations —
schema creation, inserting results, managing the contest name registry,
flags, and overrides.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from dupage_elections.normalize import normalize_contest_name, normalize_party

DEFAULT_DB_PATH = Path("elections.db")

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS results (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        contest_id          TEXT,
        line_number         INTEGER,
        year                INTEGER NOT NULL,
        source_file         TEXT NOT NULL,
        contest_name_raw    TEXT NOT NULL,
        contest_name        TEXT NOT NULL,
        choice_name         TEXT,
        party               TEXT,
        total_votes         REAL,
        percent_of_votes    REAL,
        registered_voters   REAL,
        ballots_cast        REAL,
        num_precinct_total  REAL,
        num_precinct_rptg   REAL,
        over_votes          REAL,
        under_votes         REAL
    );

    CREATE TABLE IF NOT EXISTS contest_names (
        contest_name        TEXT PRIMARY KEY,
        first_seen_year     INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS contest_name_flags (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        year                INTEGER NOT NULL,
        contest_name_raw    TEXT NOT NULL,
        contest_name        TEXT NOT NULL,
        resolved            INTEGER NOT NULL DEFAULT 0,
        flagged_at          TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS contest_name_overrides (
        contest_name_raw    TEXT PRIMARY KEY,
        contest_name        TEXT NOT NULL,
        note                TEXT
    );

    CREATE TABLE IF NOT EXISTS loaded_sources (
        filename            TEXT PRIMARY KEY,
        year                INTEGER NOT NULL,
        loaded_at           TEXT DEFAULT (datetime('now'))
    );
"""

_RESULT_COLUMNS = [
    "contest_id", "line_number", "year", "source_file",
    "contest_name_raw", "contest_name", "choice_name",
    "party", "total_votes", "percent_of_votes", "registered_voters",
    "ballots_cast", "num_precinct_total", "num_precinct_rptg",
    "over_votes", "under_votes",
]

_INSERT_RESULT_SQL = f"""
    INSERT INTO results ({', '.join(_RESULT_COLUMNS)})
    VALUES ({', '.join(['?'] * len(_RESULT_COLUMNS))})
"""


class ElectionDatabase:
    """
    Manages the elections SQLite database.

    Owns all read/write operations: inserting results, registering contest
    names, flagging unrecognized names, and managing overrides.

    Usage:
        db = ElectionDatabase()                        # default path
        db = ElectionDatabase(Path("my/path.db"))      # custom path
        db = ElectionDatabase(Path(":memory:"))        # in-memory (testing)
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Source file registry
    # ------------------------------------------------------------------

    def is_source_loaded(self, filename: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM loaded_sources WHERE filename = ?", (filename,)
        ).fetchone()
        return row is not None

    def register_source(self, filename: str, year: int) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO loaded_sources (filename, year) VALUES (?,?)",
            (filename, year),
        )
        self._conn.commit()

    def get_loaded_sources(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT filename, year, loaded_at FROM loaded_sources ORDER BY year, filename"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Contest name registry
    # ------------------------------------------------------------------

    def get_known_contest_names(self) -> set[str]:
        rows = self._conn.execute("SELECT contest_name FROM contest_names").fetchall()
        return {r[0] for r in rows}

    def register_contest_name(self, name: str, year: int) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO contest_names (contest_name, first_seen_year) VALUES (?,?)",
            (name, year),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def get_overrides(self) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT contest_name_raw, contest_name FROM contest_name_overrides"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def add_override(self, raw_name: str, canonical_name: str, note: str | None = None) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO contest_name_overrides (contest_name_raw, contest_name, note) VALUES (?,?,?)",
            (raw_name, canonical_name, note),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def get_unresolved_flags(self) -> list[dict]:
        rows = self._conn.execute("""
            SELECT id, year, contest_name_raw, contest_name
            FROM contest_name_flags
            WHERE resolved = 0
            ORDER BY year, contest_name
        """).fetchall()
        return [dict(r) for r in rows]

    def resolve_flag(self, flag_id: int) -> None:
        self._conn.execute(
            "UPDATE contest_name_flags SET resolved = 1 WHERE id = ?",
            (flag_id,),
        )
        self._conn.commit()

    def _write_flags(self, df: pd.DataFrame, new_names: list[str]) -> None:
        flag_rows = (
            df[df["contest_name"].isin(new_names)][
                ["year", "contest_name_raw", "contest_name"]
            ]
            .drop_duplicates()
            .itertuples(index=False)
        )
        self._conn.executemany(
            "INSERT INTO contest_name_flags (year, contest_name_raw, contest_name) VALUES (?,?,?)",
            flag_rows,
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Inserting results
    # ------------------------------------------------------------------

    def insert_results(
        self,
        df: pd.DataFrame,
        year: int,
        source_file: str,
    ) -> tuple[int, list[str]]:
        """
        Normalize and insert a DataFrame of election results.

        Applies contest name normalization (with override lookups), normalizes
        party codes, flags any unrecognized contest names, and registers all
        new contest names in the registry.

        Args:
            df:          DataFrame with at least 'contest_name_raw' and 'party' columns.
            year:        Election year.
            source_file: Filename of the source (stored for provenance).

        Returns:
            (rows_inserted, list_of_new_unrecognized_contest_names)
        """
        known = self.get_known_contest_names()
        overrides = self.get_overrides()

        df = df.copy()
        df["year"] = year
        df["source_file"] = source_file
        df["contest_name_raw"] = df["contest_name_raw"].astype(str)
        df["contest_name"] = df["contest_name_raw"].apply(
            lambda r: overrides[r] if r in overrides else normalize_contest_name(r)
        )
        df["party"] = df["party"].apply(normalize_party)
        if "line_number" not in df.columns:
            df["line_number"] = None
        df["contest_id"] = df.apply(
            lambda r: f"{int(r['year'])}-{int(r['line_number'])}"
            if r["line_number"] is not None and not pd.isna(r["line_number"])
            else None,
            axis=1,
        )

        new_names = sorted(set(df["contest_name"].unique()) - known)

        rows = [
            (
                row.get("contest_id"),
                int(row["line_number"]) if row.get("line_number") is not None and not pd.isna(row.get("line_number")) else None,
                int(row["year"]),
                row["source_file"],
                row["contest_name_raw"],
                row["contest_name"],
                row.get("choice_name"),
                row.get("party"),
                row.get("total_votes"),
                row.get("percent_of_votes"),
                row.get("registered_voters"),
                row.get("ballots_cast"),
                row.get("num_precinct_total"),
                row.get("num_precinct_rptg"),
                row.get("over_votes"),
                row.get("under_votes"),
            )
            for _, row in df.iterrows()
        ]

        self._conn.executemany(_INSERT_RESULT_SQL, rows)

        if new_names:
            self._write_flags(df, new_names)

        for name in df["contest_name"].unique():
            self._conn.execute(
                "INSERT OR IGNORE INTO contest_names (contest_name, first_seen_year) VALUES (?,?)",
                (name, year),
            )

        self._conn.commit()
        return len(rows), new_names

    # ------------------------------------------------------------------
    # Read access (for analysis)
    # ------------------------------------------------------------------

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        """Execute a SELECT and return results as a DataFrame."""
        return pd.read_sql(sql, self._conn, params=params or [])
