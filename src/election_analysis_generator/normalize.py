"""
normalize.py
------------
Contest name and party normalization logic.

Keeping this in its own module makes it easy to unit test independently
of any database or file I/O.
"""

import re
import pandas as pd

# ---------------------------------------------------------------------------
# Contest name normalization
# ---------------------------------------------------------------------------

# Ordinal words that appear in contest names (add more as needed).
# Keys are lowercase; values are their spelled-out equivalents.
ORDINAL_MAP: dict[str, str] = {
    "1st": "first",
    "2nd": "second",
    "3rd": "third",
    "4th": "fourth",
    "5th": "fifth",
    "6th": "sixth",
    "7th": "seventh",
    "8th": "eighth",
    "9th": "ninth",
    "10th": "tenth",
    "11th": "eleventh",
    "12th": "twelfth",
    "21st": "twenty-first",
    "22nd": "twenty-second",
    "23rd": "twenty-third",
    "24th": "twenty-fourth",
    "39th": "thirty-ninth",
    "41st": "forty-first",
    "42nd": "forty-second",
    "45th": "forty-fifth",
    "48th": "forty-eighth",
    "49th": "forty-ninth",
    "50th": "fiftieth",
    "56th": "fifty-sixth",
    "65th": "sixty-fifth",
    "77th": "seventy-seventh",
    "81st": "eighty-first",
    "82nd": "eighty-second",
    "84th": "eighty-fourth",
    "85th": "eighty-fifth",
}

_ORDINAL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in ORDINAL_MAP) + r")\b",
    flags=re.IGNORECASE,
)


def normalize_contest_name(raw_name: str) -> str:
    """
    Normalize a contest name for consistent cross-year comparison.

    Transformations applied in order:
      1. Strip party suffixes: " - D*", " - R*", " -D", " - R", etc.
      2. Strip trailing parentheticals: "(Vote For 1)", "(To fill the vacancy...)"
      3. Strip term-length suffixes: "Full 4 Year Term", "4 Year Term", etc.
      4. Uppercase
      5. Gender-neutral titles: committeeman/woman → committeeperson, etc.
      6. Spell out ordinal numerals: "81st" → "EIGHTY-FIRST"
         (plain integers like "District 1" are preserved)
    """
    name = raw_name.strip()

    # 1. Strip party suffixes (before uppercasing to catch mixed case)
    name = re.sub(r"\s*-\s*[DR]\*?\s*$", "", name, flags=re.IGNORECASE)

    # 2. Strip trailing parentheticals; repeat to handle multiple/nested ones
    for _ in range(3):
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()

    # 3. Strip term-length suffixes (with optional leading comma or dash)
    #    e.g. "District 1, 4 Year Term - R" -> "District 1"
    name = re.sub(
        r"[,]?\s*-?\s*Full\s+\d+\s+Year\s+Term\s*$", "", name, flags=re.IGNORECASE
    ).strip()
    name = re.sub(
        r"[,]?\s*-?\s*\d+\s+Year\s+Term\s*$", "", name, flags=re.IGNORECASE
    ).strip()

    # 4. Uppercase
    name = name.upper()

    # 5. Gender-neutral titles
    replacements = [
        (r"\bCOMMITTEEMAN\b", "COMMITTEEPERSON"),
        (r"\bCOMMITTEEWOMAN\b", "COMMITTEEPERSON"),
        (r"\bCONGRESSMAN\b", "CONGRESSPERSON"),
        (r"\bCONGRESSWOMAN\b", "CONGRESSPERSON"),
        (r"\bCHAIRMAN\b", "CHAIRPERSON"),
        (r"\bCHAIRWOMAN\b", "CHAIRPERSON"),
    ]
    for pattern, replacement in replacements:
        name = re.sub(pattern, replacement, name)

    # 6. Spell out ordinal numerals
    def _replace_ordinal(m: re.Match) -> str:
        return ORDINAL_MAP[m.group(0).lower()].upper()

    name = _ORDINAL_PATTERN.sub(_replace_ordinal, name)

    return name


# ---------------------------------------------------------------------------
# Party normalization
# ---------------------------------------------------------------------------

# CSVs use single-letter codes; Excel history uses full abbreviations.
PARTY_MAP: dict[str, str] = {
    "D": "DEM",
    "R": "REP",
    "DEM": "DEM",
    "REP": "REP",
    "GP": "GP",
    "WC": "WC",
}


def normalize_party(raw: str | None) -> str | None:
    """Normalize a raw party code to a canonical abbreviation, or None if blank."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    cleaned = str(raw).strip().upper()
    return PARTY_MAP.get(cleaned, cleaned)


# ---------------------------------------------------------------------------
# Candidate name normalization
# ---------------------------------------------------------------------------

def _strip_punctuation(name: str) -> str:
    """Strip all non-alpha characters from a name and uppercase it.

    Used to normalise candidate names for lookup purposes only — the
    original value is always preserved for storage.  Handles initials
    with dots, hyphens, spaces between letters, apostrophes, etc.
    """
    return re.sub(r"[^A-Za-z]", "", name).upper()


# Maps (normalized_first, normalized_last) -> (correct_first, correct_last).
# Either element of the value tuple may be None to leave that field unchanged.
# Add further entries here as new data-quality issues are discovered.
_NAME_CORRECTIONS: dict[tuple[str, str], tuple[str | None, str | None]] = {
    ("JB", "PRITZER"): (None, "PRITZKER"),
}


def normalize_candidate_names(first_name: str, last_name: str) -> tuple[str, str]:
    """
    Preserve original first_name/last_name when returning values unless a
    correction explicitly provides a replacement. Use stripped (uppercased,
    punctuation-removed) forms only for lookup/comparison.
    """
    # Keep original forms (but normalize case for stable returns if desired)
    out_first = first_name
    out_last = last_name

    # Stripped forms used only for lookup
    stripped_first = _strip_punctuation(first_name)
    stripped_last = _strip_punctuation(last_name)

    # Lookup by stripped forms and apply corrections if present.
    correction = _NAME_CORRECTIONS.get((stripped_first, stripped_last))
    if correction is not None:
        corrected_first, corrected_last = correction
        if corrected_first is not None:
            out_first = corrected_first
        if corrected_last is not None:
            out_last = corrected_last

    return out_first, out_last
