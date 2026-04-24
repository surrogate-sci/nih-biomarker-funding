import csv
import tempfile
import unittest
from pathlib import Path


class TestAssignRate(unittest.TestCase):
    def test_ca_gets_5_percent(self):
        from scripts.sample_grants import assign_rate

        self.assertAlmostEqual(assign_rate("CA", 66000), 0.05)

    def test_large_ic_gets_7_percent(self):
        from scripts.sample_grants import assign_rate

        self.assertAlmostEqual(assign_rate("HL", 23000), 0.07)
        self.assertAlmostEqual(assign_rate("AG", 22000), 0.07)

    def test_small_ic_gets_10_percent(self):
        from scripts.sample_grants import assign_rate

        self.assertAlmostEqual(assign_rate("DA", 7000), 0.10)
        self.assertAlmostEqual(assign_rate("AR", 6000), 0.10)

    def test_boundary_20k(self):
        from scripts.sample_grants import assign_rate

        self.assertAlmostEqual(assign_rate("XX", 20000), 0.07)  # >=20K = 7%
        self.assertAlmostEqual(assign_rate("XX", 19999), 0.10)  # <20K = 10%


class TestStratifiedSample(unittest.TestCase):
    def test_respects_min_per_stratum(self):
        from scripts.sample_grants import stratified_sample

        rows = [
            {"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "XX"}
            for i in range(10)
        ]
        sampled = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        self.assertEqual(len(sampled), 10)  # can't exceed pool

    def test_rate_applied(self):
        from scripts.sample_grants import stratified_sample

        rows = [
            {"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "CA"}
            for i in range(1000)
        ]
        sampled = stratified_sample(rows, rate=0.05, min_per_stratum=25, seed=42)
        self.assertAlmostEqual(len(sampled), 50, delta=5)

    def test_reproducible_with_seed(self):
        from scripts.sample_grants import stratified_sample

        rows = [
            {"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "CA"}
            for i in range(1000)
        ]
        s1 = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        s2 = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        ids1 = [r["APPLICATION_ID"] for r in s1]
        ids2 = [r["APPLICATION_ID"] for r in s2]
        self.assertEqual(ids1, ids2)

    def test_stratifies_by_fy(self):
        from scripts.sample_grants import stratified_sample

        rows = []
        for fy in ["2020", "2021"]:
            rows.extend(
                [
                    {"APPLICATION_ID": f"{fy}_{i}", "FY": fy, "ADMINISTERING_IC": "CA"}
                    for i in range(200)
                ]
            )
        sampled = stratified_sample(rows, rate=0.10, min_per_stratum=10, seed=42)
        fys = [r["FY"] for r in sampled]
        # Both years should be represented
        self.assertIn("2020", fys)
        self.assertIn("2021", fys)


class TestLoadGrantsP30Filter(unittest.TestCase):
    """Tests for P30 exclusion logic in load_grants."""

    _FIELDNAMES = [
        "APPLICATION_ID", "FY", "ADMINISTERING_IC", "ACTIVITY",
        "NIH_SPENDING_CATS", "PROJECT_TITLE", "TOTAL_COST",
        "EXPLICIT_BIOMARKER", "MATCH_SOURCE",
    ]

    def _make_csv(self, rows: list[dict], path: Path) -> None:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({**{k: "" for k in self._FIELDNAMES}, **row})

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        self.tmp.close()
        self.csv_path = Path(self.tmp.name)

    def tearDown(self):
        self.csv_path.unlink(missing_ok=True)

    def test_p30_without_clinical_is_filtered(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "1", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P30", "NIH_SPENDING_CATS": "Cancer;Basic Science"},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 0)

    def test_p30_with_clinical_is_kept(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "2", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P30", "NIH_SPENDING_CATS": "Clinical Research;Cancer"},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 1)

    def test_p30_empty_spending_cats_is_filtered(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "3", "FY": "2004", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P30", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 0)

    def test_r01_always_kept(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "4", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "R01", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 1)

    def test_p01_and_p50_always_kept(self):
        """Other P-mechanism grants (P01, P50) are NOT filtered."""
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "5", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P01", "NIH_SPENDING_CATS": "Basic Science"},
            {"APPLICATION_ID": "6", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P50", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 2)

    def test_u54_always_kept(self):
        """U grants are not filtered regardless of spending cats."""
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "7", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "U54", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
