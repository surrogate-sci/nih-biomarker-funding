"""Tests for abstract-text supplementation logic."""

import unittest


class TestFindNewGrants(unittest.TestCase):
    def test_finds_new_grant(self):
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        existing_ids = {"111"}
        abstracts = {
            "111": "existing biomarker grant",
            "222": "new biomarker discovery study",
            "333": "unrelated cancer treatment",
        }
        new_grants = find_new_grants_from_abstracts(abstracts, existing_ids)
        self.assertIn("222", new_grants)
        self.assertNotIn("111", new_grants)
        self.assertNotIn("333", new_grants)

    def test_sets_explicit_biomarker_flag(self):
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        abstracts = {
            "100": "This studies a specific biomarker for disease",
            "200": "Clinical imaging analysis of tumors",  # matches clinical+imaging
        }
        new_grants = find_new_grants_from_abstracts(abstracts, set())
        self.assertEqual(new_grants["100"]["EXPLICIT_BIOMARKER"], "TRUE")
        self.assertEqual(new_grants["200"]["EXPLICIT_BIOMARKER"], "FALSE")

    def test_empty_abstracts(self):
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        new_grants = find_new_grants_from_abstracts({}, set())
        self.assertEqual(len(new_grants), 0)

    def test_custom_terms(self):
        """Custom expanded/core terms override defaults."""
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        abstracts = {
            "500": "study of novel proteomics approach",
            "501": "biomarker validation trial",
        }
        new_grants = find_new_grants_from_abstracts(
            abstracts,
            set(),
            expanded_terms=["proteomics"],
            core_terms=["proteomics"],
        )
        self.assertIn("500", new_grants)
        self.assertEqual(new_grants["500"]["EXPLICIT_BIOMARKER"], "TRUE")
        self.assertNotIn("501", new_grants)  # "biomarker" not in custom terms

    def test_skips_empty_abstract_text(self):
        """Grants with empty abstract text should not match."""
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        abstracts = {
            "600": "",
            "601": "   ",
        }
        new_grants = find_new_grants_from_abstracts(abstracts, set())
        self.assertEqual(len(new_grants), 0)

    def test_and_condition_in_abstract(self):
        """Expanded terms with + (AND) conditions should work on abstract text."""
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        abstracts = {
            "700": "clinical proteomics and omics analysis",  # matches clinical+omics
            "701": "omics analysis only",  # missing "clinical"
        }
        new_grants = find_new_grants_from_abstracts(abstracts, set())
        self.assertIn("700", new_grants)
        self.assertNotIn("701", new_grants)


class TestAssignMatchSource(unittest.TestCase):
    def test_keywords_only(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="100", in_keyword_filter=True, abstract_text="unrelated study"
        )
        self.assertEqual(result, "keywords_only")

    def test_abstract_only(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="200",
            in_keyword_filter=False,
            abstract_text="biomarker validation study",
        )
        self.assertEqual(result, "abstract_only")

    def test_keyword_abstract(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="300",
            in_keyword_filter=True,
            abstract_text="biomarker discovery project",
        )
        self.assertEqual(result, "keyword_abstract")

    def test_no_abstract(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="400", in_keyword_filter=True, abstract_text=""
        )
        self.assertEqual(result, "keywords_only")

    def test_no_match_neither(self):
        """Grant not in keyword filter and abstract has no terms -> None."""
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="500", in_keyword_filter=False, abstract_text="unrelated study"
        )
        self.assertIsNone(result)

    def test_custom_terms(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="600",
            in_keyword_filter=False,
            abstract_text="proteomics study",
            expanded_terms=["proteomics"],
        )
        self.assertEqual(result, "abstract_only")


if __name__ == "__main__":
    unittest.main()
