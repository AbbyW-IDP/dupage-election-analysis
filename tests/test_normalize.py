"""
Tests for election_analysis.normalize
"""

import pytest
from src.election_analysis_generator.normalize import (
    normalize_contest_name,
    normalize_candidate_names,
    normalize_party,
)


class TestNormalizeContestName:
    def test_uppercase(self):
        assert normalize_contest_name("for attorney general") == "FOR ATTORNEY GENERAL"

    def test_strips_vote_for_parenthetical(self):
        assert (
            normalize_contest_name("FOR ATTORNEY GENERAL (Vote For 1)")
            == "FOR ATTORNEY GENERAL"
        )

    def test_strips_vacancy_parenthetical(self):
        result = normalize_contest_name(
            "FOR JUDGE OF THE CIRCUIT COURT (To fill the vacancy of the Honorable Jane Smith) (Vote For 1)"
        )
        assert result == "FOR JUDGE OF THE CIRCUIT COURT"

    def test_strips_party_suffix_d_star(self):
        assert (
            normalize_contest_name("United States Senator - D*")
            == "UNITED STATES SENATOR"
        )

    def test_strips_party_suffix_r_star(self):
        assert normalize_contest_name("FOR SENATOR - R*") == "FOR SENATOR"

    def test_strips_party_suffix_bare(self):
        assert normalize_contest_name("FOR SENATOR - R") == "FOR SENATOR"

    def test_strips_full_year_term(self):
        assert (
            normalize_contest_name(
                "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1 FULL 4 YEAR TERM (Vote For 1)"
            )
            == "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1"
        )

    def test_strips_full_2_year_term(self):
        assert (
            normalize_contest_name(
                "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1 FULL 2 YEAR TERM (Vote For 1)"
            )
            == "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1"
        )

    def test_strips_year_term_with_party_suffix(self):
        assert (
            normalize_contest_name(
                "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1 4 Year Term - R"
            )
            == "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1"
        )

    def test_committeeman_to_committeeperson(self):
        assert (
            normalize_contest_name("FOR PRECINCT COMMITTEEMAN YORK 050 (Vote For 1)")
            == "FOR PRECINCT COMMITTEEPERSON YORK 050"
        )

    def test_committeewoman_to_committeeperson(self):
        assert (
            normalize_contest_name("FOR PRECINCT COMMITTEEWOMAN YORK 050 (Vote For 1)")
            == "FOR PRECINCT COMMITTEEPERSON YORK 050"
        )

    def test_congressman_to_congressperson(self):
        assert (
            normalize_contest_name("FOR CONGRESSMAN EIGHTH DISTRICT (Vote For 1)")
            == "FOR CONGRESSPERSON EIGHTH DISTRICT"
        )

    def test_chairman_to_chairperson(self):
        assert (
            normalize_contest_name("FOR CHAIRMAN OF THE COUNTY BOARD (Vote For 1)")
            == "FOR CHAIRPERSON OF THE COUNTY BOARD"
        )

    def test_ordinal_81st(self):
        assert (
            normalize_contest_name(
                "FOR REPRESENTATIVE IN THE GENERAL ASSEMBLY 81ST REPRESENTATIVE DISTRICT (Vote For 1)"
            )
            == "FOR REPRESENTATIVE IN THE GENERAL ASSEMBLY EIGHTY-FIRST REPRESENTATIVE DISTRICT"
        )

    def test_ordinal_3rd(self):
        assert (
            normalize_contest_name(
                "FOR REPRESENTATIVE IN CONGRESS 3RD CONGRESSIONAL DISTRICT (Vote For 1)"
            )
            == "FOR REPRESENTATIVE IN CONGRESS THIRD CONGRESSIONAL DISTRICT"
        )

    def test_preserves_plain_integers(self):
        assert (
            normalize_contest_name(
                "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1 (Vote For 1)"
            )
            == "FOR MEMBER OF THE COUNTY BOARD DISTRICT 1"
        )

    def test_strips_all_transformations_combined(self):
        assert (
            normalize_contest_name("For Precinct Committeewoman York 050 (Vote For 1)")
            == "FOR PRECINCT COMMITTEEPERSON YORK 050"
        )

    def test_whitespace_trimmed(self):
        assert (
            normalize_contest_name("  FOR ATTORNEY GENERAL  ") == "FOR ATTORNEY GENERAL"
        )


class TestNormalizeParty:
    def test_d_to_dem(self):
        assert normalize_party("D") == "DEM"

    def test_r_to_rep(self):
        assert normalize_party("R") == "REP"

    def test_dem_passthrough(self):
        assert normalize_party("DEM") == "DEM"

    def test_rep_passthrough(self):
        assert normalize_party("REP") == "REP"

    def test_lowercase(self):
        assert normalize_party("d") == "DEM"

    def test_gp_passthrough(self):
        assert normalize_party("GP") == "GP"

    def test_wc_passthrough(self):
        assert normalize_party("WC") == "WC"

    def test_none_returns_none(self):
        assert normalize_party(None) is None

    def test_nan_returns_none(self):
        import math

        assert normalize_party(float("nan")) is None

    def test_unknown_party_returned_as_is(self):
        assert normalize_party("LIB") == "LIB"


class TestNormalizeCandidateName:
    # --- Punctuation stripping ---

    def test_dots_stripped_from_initials(self):
        """'J.B.' → 'JB' after punctuation stripping."""
        assert normalize_candidate_names("J.B.", "PRITZKER") == ("JB", "PRITZKER")

    def test_no_punctuation_name_unchanged(self):
        """A name with no punctuation is returned as-is (modulo case)."""
        first, last = normalize_candidate_names("JB", "PRITZKER")
        assert first == "JB"

    def test_hyphenated_last_name_stripped(self):
        """Hyphens are stripped from last names."""
        assert normalize_candidate_names("Jane", "Smith-Jones") == ("Jane", "SMITHJONES")

    def test_apostrophe_stripped(self):
        """Apostrophes are stripped (e.g. O'Brien → OBRIEN)."""
        assert normalize_candidate_names("Pat", "O'Brien") == ("Pat", "OBRIEN")

    def test_spaces_between_initials_stripped(self):
        """'J. B.' (space between initials) → 'JB'."""
        first, _ = normalize_candidate_names("J. B.", "PRITZKER")
        assert first == "JB"

    def test_plain_name_with_no_punctuation_case_preserved(self):
        """A plain name with no punctuation keeps its original casing."""
        assert normalize_candidate_names("Jane", "Smith") == ("Jane", "Smith")

    # --- Pritzker last-name correction ---

    def test_jb_no_dots_corrects_last_name(self):
        """'JB PRITZER' → last name corrected to PRITZKER."""
        assert normalize_candidate_names("JB", "PRITZER") == ("JB", "PRITZKER")

    def test_jb_with_dots_corrects_last_name(self):
        """'J.B. PRITZER' → punctuation stripped and last name corrected."""
        assert normalize_candidate_names("J.B.", "PRITZER") == ("JB", "PRITZKER")

    def test_jb_lowercase_corrects_last_name(self):
        """Lowercase 'jb' is normalised and last name corrected."""
        assert normalize_candidate_names("jb", "PRITZER") == ("JB", "PRITZKER")

    def test_jb_mixed_case_last_name_corrected(self):
        """Mixed-case 'Pritzer' is corrected."""
        assert normalize_candidate_names("JB", "Pritzer") == ("JB", "PRITZKER")

    def test_jb_with_spaces_between_initials_corrects_last_name(self):
        """'J. B.' with space between initials triggers correction."""
        assert normalize_candidate_names("J. B.", "PRITZER") == ("JB", "PRITZKER")

    # --- Correction dict supports first-name-only and both-name corrections ---

    def test_correction_can_fix_first_name(self, monkeypatch):
        """A correction entry with a non-None first value updates first_name."""
        from src.election_analysis_generator import normalize as norm
        monkeypatch.setitem(norm._NAME_CORRECTIONS, ("BOB", "DOE"), ("ROBERT", None))
        assert norm.normalize_candidate_names("BOB", "DOE") == ("ROBERT", "DOE")

    def test_correction_can_fix_both_names(self, monkeypatch):
        """A correction entry can update both first and last name."""
        from src.election_analysis_generator import normalize as norm
        monkeypatch.setitem(norm._NAME_CORRECTIONS, ("BOB", "DOE"), ("ROBERT", "DOUGH"))
        assert norm.normalize_candidate_names("BOB", "DOE") == ("ROBERT", "DOUGH")

    # --- Non-matching cases — nothing corrected ---

    def test_different_first_name_not_corrected(self):
        """A different first name with the misspelled last name is left alone."""
        assert normalize_candidate_names("Janet", "PRITZER") == ("Janet", "PRITZER")

    def test_correct_spelling_unchanged(self):
        """Already-correct spelling is passed through untouched."""
        assert normalize_candidate_names("JB", "PRITZKER") == ("JB", "PRITZKER")

    def test_unrelated_candidate_unchanged(self):
        """A completely unrelated name is returned as-is."""
        assert normalize_candidate_names("Jane", "Smith") == ("Jane", "Smith")
