"""Tests for keyword matching logic."""
import unittest


class TestContainsBiomarkerTerms(unittest.TestCase):
    def test_simple_match(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertTrue(contains_biomarker_terms("This is a biomarker study", ["biomarker"]))

    def test_no_match(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms("This is a cancer study", ["biomarker"]))

    def test_and_condition_match(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertTrue(contains_biomarker_terms("clinical omics study", ["clinical+omics"]))

    def test_and_condition_partial(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms("clinical study", ["clinical+omics"]))

    def test_case_insensitive(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertTrue(contains_biomarker_terms("BIOMARKER study", ["biomarker"]))

    def test_empty_text(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms("", ["biomarker"]))

    def test_none_text(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms(None, ["biomarker"]))

    def test_core_terms_defined(self):
        from scripts.keyword_terms import CORE_BIOMARKER_TERMS
        self.assertEqual(len(CORE_BIOMARKER_TERMS), 13)
        self.assertIn("biomarker", CORE_BIOMARKER_TERMS)

    def test_expanded_terms_defined(self):
        from scripts.keyword_terms import EXPANDED_BIOMARKER_TERMS
        self.assertEqual(len(EXPANDED_BIOMARKER_TERMS), 36)
        self.assertIn("endophenotype", EXPANDED_BIOMARKER_TERMS)


class TestPrimaryTerm(unittest.TestCase):
    def test_specific_wins_over_generic(self):
        from scripts.keyword_terms import primary_term
        self.assertEqual(primary_term(["biomarker", "surrogate endpoint"]), "surrogate endpoint")

    def test_imaging_marker_over_biomarker(self):
        from scripts.keyword_terms import primary_term
        self.assertEqual(primary_term(["biomarker", "imaging marker"]), "imaging marker")

    def test_clinical_omics_over_biomarker(self):
        from scripts.keyword_terms import primary_term
        self.assertEqual(primary_term(["biomarker", "clinical+omics"]), "clinical+omics")

    def test_single_term(self):
        from scripts.keyword_terms import primary_term
        self.assertEqual(primary_term(["biomarker"]), "biomarker")

    def test_empty_list(self):
        from scripts.keyword_terms import primary_term
        self.assertEqual(primary_term([]), "")

    def test_biomarker_is_lowest_priority(self):
        from scripts.keyword_terms import primary_term, TERM_PRIORITY
        # biomarker should be last in priority
        self.assertEqual(TERM_PRIORITY[-1], "biomarker")

    def test_all_expanded_terms_in_priority(self):
        from scripts.keyword_terms import TERM_PRIORITY, EXPANDED_BIOMARKER_TERMS
        for term in EXPANDED_BIOMARKER_TERMS:
            self.assertIn(term, TERM_PRIORITY, f"{term} missing from TERM_PRIORITY")


if __name__ == "__main__":
    unittest.main()
