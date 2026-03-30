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
        self.assertEqual(len(CORE_BIOMARKER_TERMS), 4)
        self.assertIn("biomarker", CORE_BIOMARKER_TERMS)

    def test_expanded_terms_defined(self):
        from scripts.keyword_terms import EXPANDED_BIOMARKER_TERMS
        self.assertEqual(len(EXPANDED_BIOMARKER_TERMS), 10)
        self.assertIn("endophenotype", EXPANDED_BIOMARKER_TERMS)


if __name__ == "__main__":
    unittest.main()
