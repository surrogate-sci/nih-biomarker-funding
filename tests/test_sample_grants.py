import unittest


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
        rows = [{"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "XX"} for i in range(10)]
        sampled = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        self.assertEqual(len(sampled), 10)  # can't exceed pool

    def test_rate_applied(self):
        from scripts.sample_grants import stratified_sample
        rows = [{"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "CA"} for i in range(1000)]
        sampled = stratified_sample(rows, rate=0.05, min_per_stratum=25, seed=42)
        self.assertAlmostEqual(len(sampled), 50, delta=5)

    def test_reproducible_with_seed(self):
        from scripts.sample_grants import stratified_sample
        rows = [{"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "CA"} for i in range(1000)]
        s1 = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        s2 = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        ids1 = [r["APPLICATION_ID"] for r in s1]
        ids2 = [r["APPLICATION_ID"] for r in s2]
        self.assertEqual(ids1, ids2)

    def test_stratifies_by_fy(self):
        from scripts.sample_grants import stratified_sample
        rows = []
        for fy in ["2020", "2021"]:
            rows.extend([{"APPLICATION_ID": f"{fy}_{i}", "FY": fy, "ADMINISTERING_IC": "CA"} for i in range(200)])
        sampled = stratified_sample(rows, rate=0.10, min_per_stratum=10, seed=42)
        fys = [r["FY"] for r in sampled]
        # Both years should be represented
        self.assertIn("2020", fys)
        self.assertIn("2021", fys)


if __name__ == "__main__":
    unittest.main()
