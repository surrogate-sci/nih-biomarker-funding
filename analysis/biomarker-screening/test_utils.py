"""Tests for biomarker screening analysis utilities."""

import sys
import unittest
from pathlib import Path

# Ensure the analysis directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_QUALITY_YEARS, activity_category, load_dataset


class TestLoadDataset(unittest.TestCase):
    def test_load_returns_dataframe_with_expected_columns(self):
        df = load_dataset()
        for col in [
            "FY",
            "TOTAL_COST",
            "ADMINISTERING_IC",
            "EXPLICIT_BIOMARKER",
            "ACTIVITY",
        ]:
            self.assertIn(col, df.columns)

    def test_load_has_expected_row_count(self):
        df = load_dataset()
        self.assertGreater(len(df), 320_000)
        self.assertLess(len(df), 340_000)

    def test_explicit_biomarker_is_boolean(self):
        df = load_dataset()
        self.assertEqual(df["EXPLICIT_BIOMARKER"].dtype, bool)

    def test_total_cost_is_numeric(self):
        df = load_dataset()
        self.assertIn(str(df["TOTAL_COST"].dtype), ["float64", "int64"])


class TestDataQualityYears(unittest.TestCase):
    def test_data_quality_years_constant(self):
        self.assertIn(2005, DATA_QUALITY_YEARS)
        self.assertIn(2006, DATA_QUALITY_YEARS)


class TestActivityCategory(unittest.TestCase):
    def test_r_series(self):
        self.assertEqual(activity_category("R01"), "Research (R)")

    def test_u_series(self):
        self.assertEqual(activity_category("U01"), "Cooperative (U)")

    def test_missing(self):
        self.assertEqual(activity_category(""), "Other")
        self.assertEqual(activity_category(None), "Other")


if __name__ == "__main__":
    unittest.main()
