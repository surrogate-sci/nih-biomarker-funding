"""Tests for generate_review.py — data loading and review generation.

Focused on bugs found in production:
- ABSTRACT vs ABSTRACT_TEXT column name mismatch
- Disagreement examples missing abstracts
- Model results not joined correctly
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts/ to path so we can import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_review import (
    build_review_data,
    load_disagreement_examples,
    load_examples,
    load_model_results,
)


class TestLoadDisagreementExamples(unittest.TestCase):
    """Tests for load_disagreement_examples — the function with the ABSTRACT bug."""

    def setUp(self):
        """Create temp dir with minimal test fixtures."""
        self.tmpdir = tempfile.mkdtemp()

        # Sample CSV with ABSTRACT_TEXT column (the real column name)
        self.sample_csv = Path(self.tmpdir) / "oncology_sample_100per_year.csv"
        with open(self.sample_csv, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "FY",
                    "APPLICATION_ID",
                    "ADMINISTERING_IC",
                    "ACTIVITY",
                    "TOTAL_COST",
                    "PROJECT_TITLE",
                    "ABSTRACT_TEXT",
                    "HAS_ABSTRACT",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "FY": "2020",
                    "APPLICATION_ID": "APP001",
                    "ADMINISTERING_IC": "CA",
                    "ACTIVITY": "R01",
                    "TOTAL_COST": "500000",
                    "PROJECT_TITLE": "Biomarker Study Alpha",
                    "ABSTRACT_TEXT": "This study examines cancer biomarkers in blood samples.",
                    "HAS_ABSTRACT": "True",
                }
            )
            writer.writerow(
                {
                    "FY": "2021",
                    "APPLICATION_ID": "APP002",
                    "ADMINISTERING_IC": "CA",
                    "ACTIVITY": "R21",
                    "TOTAL_COST": "200000",
                    "PROJECT_TITLE": "Genomic Markers Beta",
                    "ABSTRACT_TEXT": "We propose to identify genomic susceptibility markers.",
                    "HAS_ABSTRACT": "True",
                }
            )

        # Grade JSONL files (two models)
        self.gemini_grades = Path(self.tmpdir) / "oncology_grades_gemini.jsonl"
        with open(self.gemini_grades, "w") as f:
            f.write(
                json.dumps(
                    {
                        "application_id": "APP001",
                        "fy": "2020",
                        "title": "Biomarker Study Alpha",
                        "model": "gemini",
                        "classification": {
                            "biomarker_use": {
                                "primary": "diagnostic",
                                "secondary": None,
                            },
                            "research_design": {
                                "primary": "observational_cohort",
                                "secondary": None,
                            },
                            "evidence_strength": {"code": "correlational"},
                            "reasoning": "Gemini reasoning for APP001",
                        },
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "application_id": "APP002",
                        "fy": "2021",
                        "title": "Genomic Markers Beta",
                        "model": "gemini",
                        "classification": {
                            "biomarker_use": {
                                "primary": "susceptibility_risk",
                                "secondary": None,
                            },
                            "research_design": {
                                "primary": "observational_retrospective",
                                "secondary": None,
                            },
                            "evidence_strength": {"code": "correlational"},
                            "reasoning": "Gemini reasoning for APP002",
                        },
                    }
                )
                + "\n"
            )

        self.gpt_grades = Path(self.tmpdir) / "oncology_grades_gpt.jsonl"
        with open(self.gpt_grades, "w") as f:
            # APP001: disagrees on dim1
            f.write(
                json.dumps(
                    {
                        "application_id": "APP001",
                        "fy": "2020",
                        "title": "Biomarker Study Alpha",
                        "model": "gpt",
                        "classification": {
                            "biomarker_use": {
                                "primary": "susceptibility_risk",
                                "secondary": None,
                            },
                            "research_design": {
                                "primary": "observational_cohort",
                                "secondary": None,
                            },
                            "evidence_strength": {"code": "experimental_weak"},
                            "reasoning": "GPT reasoning for APP001",
                        },
                    }
                )
                + "\n"
            )
            # APP002: error record — should not appear as graded
            f.write(
                json.dumps(
                    {
                        "application_id": "APP002",
                        "fy": "2021",
                        "title": "Genomic Markers Beta",
                        "model": "gpt",
                        "error": "API timeout",
                    }
                )
                + "\n"
            )

        # Disagreement examples JSON
        self.disagreements_json = Path(self.tmpdir) / "disagreement_examples.json"
        with open(self.disagreements_json, "w") as f:
            json.dump(
                {
                    "extracted_at": "2026-03-04",
                    "patterns": [
                        {
                            "dimension": "dim1",
                            "code_a": "diagnostic",
                            "code_b": "susceptibility_risk",
                            "total_disagreements": 1,
                            "examples": [
                                {
                                    "application_id": "APP001",
                                    "title": "Biomarker Study Alpha",
                                    "models": {
                                        "gemini": {
                                            "dim1": "diagnostic",
                                            "reasoning": "From disagreement extract",
                                        },
                                        "gpt": {
                                            "dim1": "susceptibility_risk",
                                            "reasoning": "From disagreement extract",
                                        },
                                    },
                                }
                            ],
                        }
                    ],
                },
                f,
            )

        self.grade_files = {
            "gemini": self.gemini_grades,
            "gpt": self.gpt_grades,
        }

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_abstracts_loaded_from_sample_csv(self):
        """Critical: abstracts must come from ABSTRACT_TEXT column, not ABSTRACT."""
        review_items, model_slugs = load_disagreement_examples(
            self.disagreements_json, self.grade_files
        )
        self.assertEqual(len(review_items), 1)
        item = review_items[0]
        self.assertIn("cancer biomarkers", item["abstract"])
        self.assertNotEqual(item["abstract"], "")

    def test_metadata_joined_from_sample_csv(self):
        """Year, IC, activity, cost should come from sample CSV."""
        review_items, _ = load_disagreement_examples(
            self.disagreements_json, self.grade_files
        )
        item = review_items[0]
        self.assertEqual(item["year"], "2020")
        self.assertEqual(item["ic"], "CA")
        self.assertEqual(item["activity"], "R01")
        self.assertEqual(item["cost"], "500000")

    def test_model_results_joined(self):
        """Model classifications should be present for both models."""
        review_items, model_slugs = load_disagreement_examples(
            self.disagreements_json, self.grade_files
        )
        item = review_items[0]
        self.assertIn("gemini", item["model_results"])
        self.assertIn("gpt", item["model_results"])
        self.assertEqual(
            item["model_results"]["gemini"]["biomarker_use"]["primary"], "diagnostic"
        )
        self.assertEqual(
            item["model_results"]["gpt"]["biomarker_use"]["primary"],
            "susceptibility_risk",
        )

    def test_error_records_excluded_from_model_results(self):
        """Error records in grade JSONL must not appear as model results."""
        # APP002 has a GPT error record
        # Modify disagreements to include APP002
        with open(self.disagreements_json, "w") as f:
            json.dump(
                {
                    "extracted_at": "2026-03-04",
                    "patterns": [
                        {
                            "dimension": "dim1",
                            "code_a": "diagnostic",
                            "code_b": "susceptibility_risk",
                            "total_disagreements": 1,
                            "examples": [
                                {
                                    "application_id": "APP002",
                                    "title": "Genomic Markers Beta",
                                    "models": {},
                                }
                            ],
                        }
                    ],
                },
                f,
            )

        review_items, _ = load_disagreement_examples(
            self.disagreements_json, self.grade_files
        )
        item = review_items[0]
        # Gemini graded it, GPT errored — only gemini should appear
        self.assertIn("gemini", item["model_results"])
        self.assertNotIn("gpt", item["model_results"])

    def test_deduplication_across_patterns(self):
        """Same APPLICATION_ID appearing in multiple patterns should be deduped."""
        with open(self.disagreements_json, "w") as f:
            json.dump(
                {
                    "extracted_at": "2026-03-04",
                    "patterns": [
                        {
                            "dimension": "dim1",
                            "code_a": "diagnostic",
                            "code_b": "susceptibility_risk",
                            "total_disagreements": 1,
                            "examples": [
                                {
                                    "application_id": "APP001",
                                    "title": "Biomarker Study Alpha",
                                    "models": {},
                                }
                            ],
                        },
                        {
                            "dimension": "dim3",
                            "code_a": "correlational",
                            "code_b": "experimental_weak",
                            "total_disagreements": 1,
                            "examples": [
                                {
                                    "application_id": "APP001",
                                    "title": "Biomarker Study Alpha",
                                    "models": {},
                                }
                            ],
                        },
                    ],
                },
                f,
            )

        review_items, _ = load_disagreement_examples(
            self.disagreements_json, self.grade_files
        )
        self.assertEqual(len(review_items), 1)  # deduped


class TestBuildReviewData(unittest.TestCase):
    """Tests for build_review_data — calibration review builder."""

    def test_model_results_keyed_by_application_id(self):
        """Model results should be correctly joined by APPLICATION_ID."""
        examples = [
            {"APPLICATION_ID": "APP001", "PROJECT_TITLE": "Study A", "YEAR": "2020"},
        ]
        model_results = {
            "model_a": [
                {
                    "application_id": "APP001",
                    "classification": {
                        "biomarker_use": {"primary": "diagnostic"},
                    },
                }
            ],
        }
        review_data = build_review_data(examples, model_results)
        self.assertEqual(len(review_data), 1)
        self.assertIn("model_a", review_data[0]["model_results"])

    def test_missing_model_result_not_error(self):
        """Example with no model result should still appear, with empty model_results."""
        examples = [
            {"APPLICATION_ID": "APP999", "PROJECT_TITLE": "Ungraded", "YEAR": "2020"},
        ]
        model_results = {"model_a": []}
        review_data = build_review_data(examples, model_results)
        self.assertEqual(len(review_data), 1)
        self.assertEqual(review_data[0]["model_results"], {})


class TestCheckpointBug(unittest.TestCase):
    """Tests for run_batch_grading.py checkpoint logic.

    Critical bug: load_checkpoint() treats error records as 'done',
    meaning grants that errored are never retried.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_error_records_not_treated_as_done(self):
        """Error records in checkpoint JSONL must NOT be in the 'done' set."""
        from run_batch_grading import load_checkpoint

        checkpoint_path = Path(self.tmpdir) / "grades.jsonl"
        with open(checkpoint_path, "w") as f:
            # Successful record
            f.write(
                json.dumps(
                    {
                        "application_id": "APP001",
                        "classification": {"biomarker_use": {"primary": "diagnostic"}},
                    }
                )
                + "\n"
            )
            # Error record — should NOT be treated as done
            f.write(
                json.dumps(
                    {
                        "application_id": "APP002",
                        "error": "API timeout",
                    }
                )
                + "\n"
            )

        done = load_checkpoint(checkpoint_path)
        self.assertIn("APP001", done)
        self.assertNotIn("APP002", done)  # THIS IS THE BUG

    def test_empty_checkpoint_returns_empty_set(self):
        """Non-existent checkpoint file returns empty set."""
        from run_batch_grading import load_checkpoint

        done = load_checkpoint(Path(self.tmpdir) / "nonexistent.jsonl")
        self.assertEqual(done, set())


if __name__ == "__main__":
    unittest.main()
