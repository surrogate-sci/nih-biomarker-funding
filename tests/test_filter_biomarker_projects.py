"""Tests for filter_biomarker_projects.py — keyword matching, term tiers, facility screening.

Verifies:
- Core and expanded term sets don't cause double counting
- Facility grant screening works correctly
- contains_biomarker_terms handles single and AND conditions
- EXPLICIT_BIOMARKER flag is set correctly based on core vs expanded matches
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from filter_biomarker_projects import (
    CORE_BIOMARKER_TERMS,
    EXPANDED_BIOMARKER_TERMS,
    contains_biomarker_terms,
    is_facility_grant,
    filter_projects_csv,
)


class TestTermSets(unittest.TestCase):
    """Core is a proper subset of expanded — no grant should be counted in both."""

    def test_core_is_subset_of_expanded(self):
        core = set(CORE_BIOMARKER_TERMS)
        expanded = set(EXPANDED_BIOMARKER_TERMS)
        self.assertTrue(
            core.issubset(expanded), "Core terms must be a subset of expanded"
        )

    def test_no_duplicate_terms_in_core(self):
        self.assertEqual(len(CORE_BIOMARKER_TERMS), len(set(CORE_BIOMARKER_TERMS)))

    def test_no_duplicate_terms_in_expanded(self):
        self.assertEqual(
            len(EXPANDED_BIOMARKER_TERMS), len(set(EXPANDED_BIOMARKER_TERMS))
        )


class TestContainsBiomarkerTerms(unittest.TestCase):
    """Test the substring and AND-condition matching logic."""

    def test_simple_match(self):
        self.assertTrue(
            contains_biomarker_terms("Study of a novel biomarker", ["biomarker"])
        )

    def test_case_insensitive(self):
        self.assertTrue(contains_biomarker_terms("BIOMARKER DISCOVERY", ["biomarker"]))

    def test_substring_match(self):
        """'biomarker' matches 'predictive biomarker', 'biomarkers', etc."""
        self.assertTrue(
            contains_biomarker_terms("predictive biomarkers in cancer", ["biomarker"])
        )

    def test_no_match(self):
        self.assertFalse(
            contains_biomarker_terms("Gene regulation in mice", ["biomarker"])
        )

    def test_empty_text(self):
        self.assertFalse(contains_biomarker_terms("", ["biomarker"]))

    def test_none_text(self):
        self.assertFalse(contains_biomarker_terms(None, ["biomarker"]))

    def test_and_condition_both_present(self):
        self.assertTrue(
            contains_biomarker_terms(
                "clinical proteomics and metabolomics study", ["clinical+omics"]
            )
        )

    def test_and_condition_only_one_present(self):
        self.assertFalse(
            contains_biomarker_terms(
                "proteomics and metabolomics study", ["clinical+omics"]
            )
        )

    def test_multiple_terms_or_logic(self):
        """Any term matching is sufficient."""
        terms = ["biomarker", "surrogate endpoint"]
        self.assertTrue(
            contains_biomarker_terms("surrogate endpoint validation", terms)
        )
        self.assertTrue(contains_biomarker_terms("novel biomarker panel", terms))

    def test_marker_does_not_match_market(self):
        """'clinical marker' should not match 'marketing' or 'market'."""
        self.assertFalse(
            contains_biomarker_terms("tobacco marketing study", ["clinical marker"])
        )

    def test_new_core_terms(self):
        """New core decision-making terms match correctly."""
        self.assertTrue(
            contains_biomarker_terms(
                "risk stratification in lung cancer", ["risk stratification"]
            )
        )
        self.assertTrue(
            contains_biomarker_terms(
                "patient selection for immunotherapy", ["patient selection"]
            )
        )
        self.assertTrue(
            contains_biomarker_terms(
                "companion diagnostic for HER2", ["companion diagnostic"]
            )
        )
        self.assertTrue(
            contains_biomarker_terms(
                "predicting response to chemotherapy", ["predicting response"]
            )
        )
        self.assertTrue(
            contains_biomarker_terms(
                "tumor response to therapy", ["response to therapy"]
            )
        )

    def test_new_expanded_terms(self):
        """New expanded terms match correctly."""
        self.assertTrue(
            contains_biomarker_terms(
                "diagnostic accuracy of screening test", ["diagnostic accuracy"]
            )
        )
        self.assertTrue(
            contains_biomarker_terms(
                "theranostics in nuclear medicine", ["theranostics"]
            )
        )
        self.assertTrue(
            contains_biomarker_terms(
                "precision oncology trial design", ["precision oncology"]
            )
        )


class TestFacilityScreening(unittest.TestCase):
    """Facility grants should be excluded; research grants should not."""

    def test_administrative_core(self):
        self.assertTrue(is_facility_grant("Administrative Core"))

    def test_biostatistics_core(self):
        self.assertTrue(is_facility_grant("Biostatistics Core"))

    def test_shared_resource(self):
        self.assertTrue(is_facility_grant("Shared Resource - Tissue Bank"))

    def test_shared_facility(self):
        self.assertTrue(is_facility_grant("Tissue Procurement Shared Facility"))

    def test_labeled_core(self):
        self.assertTrue(is_facility_grant("Core C: Data Management and Bioinformatics"))

    def test_data_core(self):
        self.assertTrue(is_facility_grant("Data Core"))

    def test_research_grant_not_excluded(self):
        self.assertFalse(is_facility_grant("Risk Stratification in Lung Cancer"))

    def test_biomarker_in_title_not_excluded(self):
        self.assertFalse(
            is_facility_grant("Biomarker Discovery for Alzheimer's Disease")
        )

    def test_core_biopsy_not_excluded(self):
        """'core' in scientific context should not trigger exclusion."""
        self.assertFalse(is_facility_grant("Core biopsy findings in prostate cancer"))

    def test_empty_title(self):
        self.assertFalse(is_facility_grant(""))

    def test_none_title(self):
        self.assertFalse(is_facility_grant(None))


class TestFilterNoDoubleCounting(unittest.TestCase):
    """A grant matching both core and expanded terms should appear once in output."""

    def _make_csv(self, rows):
        """Create a temp CSV with given rows (list of dicts)."""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        )
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp.close()
        return Path(tmp.name)

    def test_grant_matching_core_appears_once(self):
        """A grant with 'biomarker' in title should appear exactly once."""
        import logging

        logger = logging.getLogger("test")

        input_csv = self._make_csv(
            [
                {
                    "APPLICATION_ID": "1001",
                    "FY": "2022",
                    "PROJECT_TITLE": "Novel biomarker for cancer",
                    "PROJECT_TERMS": "biomarker;cancer;genomics",
                    "TOTAL_COST": "500000",
                },
            ]
        )
        output_csv = Path(tempfile.mktemp(suffix=".csv"))

        try:
            stats = filter_projects_csv(
                input_csv,
                output_csv,
                logger,
                search_terms=EXPANDED_BIOMARKER_TERMS,
            )
            self.assertEqual(stats["unique_projects"], 1)

            with open(output_csv) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["EXPLICIT_BIOMARKER"], "TRUE")
        finally:
            input_csv.unlink(missing_ok=True)
            output_csv.unlink(missing_ok=True)

    def test_grant_matching_only_expanded_flagged_false(self):
        """A grant matching expanded but not core gets EXPLICIT_BIOMARKER=FALSE."""
        import logging

        logger = logging.getLogger("test")

        input_csv = self._make_csv(
            [
                {
                    "APPLICATION_ID": "2001",
                    "FY": "2022",
                    "PROJECT_TITLE": "Theranostics in nuclear medicine",
                    "PROJECT_TERMS": "theranostics;nuclear medicine",
                    "TOTAL_COST": "300000",
                },
            ]
        )
        output_csv = Path(tempfile.mktemp(suffix=".csv"))

        try:
            stats = filter_projects_csv(
                input_csv,
                output_csv,
                logger,
                search_terms=EXPANDED_BIOMARKER_TERMS,
            )
            self.assertEqual(stats["unique_projects"], 1)

            with open(output_csv) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["EXPLICIT_BIOMARKER"], "FALSE")
        finally:
            input_csv.unlink(missing_ok=True)
            output_csv.unlink(missing_ok=True)

    def test_facility_grant_excluded(self):
        """A facility grant matching biomarker terms should be excluded."""
        import logging

        logger = logging.getLogger("test")

        input_csv = self._make_csv(
            [
                {
                    "APPLICATION_ID": "3001",
                    "FY": "2022",
                    "PROJECT_TITLE": "Biostatistics Core",
                    "PROJECT_TERMS": "biomarker;statistics;data management",
                    "TOTAL_COST": "200000",
                },
            ]
        )
        output_csv = Path(tempfile.mktemp(suffix=".csv"))

        try:
            stats = filter_projects_csv(
                input_csv,
                output_csv,
                logger,
                search_terms=EXPANDED_BIOMARKER_TERMS,
            )
            self.assertEqual(stats["unique_projects"], 0)
            self.assertEqual(stats["facility_excluded"], 1)
        finally:
            input_csv.unlink(missing_ok=True)
            output_csv.unlink(missing_ok=True)

    def test_duplicate_application_id_fy_counted_once(self):
        """Same (APPLICATION_ID, FY) appearing twice should be deduplicated."""
        import logging

        logger = logging.getLogger("test")

        input_csv = self._make_csv(
            [
                {
                    "APPLICATION_ID": "4001",
                    "FY": "2022",
                    "PROJECT_TITLE": "Biomarker study",
                    "PROJECT_TERMS": "biomarker",
                    "TOTAL_COST": "100000",
                },
                {
                    "APPLICATION_ID": "4001",
                    "FY": "2022",
                    "PROJECT_TITLE": "Biomarker study",
                    "PROJECT_TERMS": "biomarker",
                    "TOTAL_COST": "100000",
                },
            ]
        )
        output_csv = Path(tempfile.mktemp(suffix=".csv"))

        try:
            stats = filter_projects_csv(
                input_csv,
                output_csv,
                logger,
                search_terms=EXPANDED_BIOMARKER_TERMS,
            )
            self.assertEqual(stats["unique_projects"], 1)
            self.assertEqual(stats["duplicates_removed"], 1)
        finally:
            input_csv.unlink(missing_ok=True)
            output_csv.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
