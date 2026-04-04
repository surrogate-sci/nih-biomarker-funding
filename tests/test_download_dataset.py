"""Tests that download-dataset.sh stays in sync with the actual dataset.

If someone updates the dataset release (new tag, new file) but forgets to
update the SHA or tag in download-dataset.sh, these tests catch it.
"""

import hashlib
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "download-dataset.sh"
DATASET_PATH = REPO_ROOT / "data" / "nih_biomarker_unified_2004-2024.csv"


def _parse_script_var(name: str) -> str:
    """Extract a variable assignment from download-dataset.sh."""
    text = SCRIPT_PATH.read_text()
    match = re.search(rf'^{name}="(.+)"', text, re.MULTILINE)
    if not match:
        raise ValueError(f"{name} not found in {SCRIPT_PATH}")
    return match.group(1)


class TestDownloadDatasetScript(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(SCRIPT_PATH.exists())

    def test_script_has_expected_sha(self):
        sha = _parse_script_var("EXPECTED_SHA")
        self.assertEqual(len(sha), 64, "EXPECTED_SHA should be a 64-char hex SHA256")

    def test_script_has_tag(self):
        tag = _parse_script_var("TAG")
        self.assertTrue(
            tag.startswith("dataset-release-"), f"Unexpected tag format: {tag}"
        )

    @unittest.skipUnless(DATASET_PATH.exists(), "dataset not downloaded")
    def test_local_dataset_matches_script_sha(self):
        """If the dataset is present locally, its SHA must match the script."""
        expected = _parse_script_var("EXPECTED_SHA")
        h = hashlib.sha256()
        with open(DATASET_PATH, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        actual = h.hexdigest()
        self.assertEqual(
            actual,
            expected,
            "Local dataset SHA doesn't match EXPECTED_SHA in download-dataset.sh. "
            "Did you update the dataset without updating the script?",
        )


if __name__ == "__main__":
    unittest.main()
