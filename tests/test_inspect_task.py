"""Tests for the Inspect AI biomarker grading task."""

import json

import pytest

from inspect_ai.dataset import Sample

from inspect_task import (
    VALID_DIM1,
    VALID_DIM2,
    VALID_DIM3,
    _INPUT_TEMPLATE,
    record_to_sample,
)
from scripts.grader_prompt import USER_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Task 2: record_to_sample tests
# ---------------------------------------------------------------------------


class TestRecordToSample:
    """Tests for the dataset loader."""

    def test_oncology_format(self):
        """Oncology CSV row maps correctly to Sample."""
        record = {
            "FY": "2020",
            "APPLICATION_ID": "12345",
            "ADMINISTERING_IC": "CA",
            "IC_NAME": "NATIONAL CANCER INSTITUTE",
            "ACTIVITY": "R01",
            "TOTAL_COST": "500000.0",
            "EXPLICIT_BIOMARKER": "True",
            "PROJECT_TITLE": "Biomarker study",
            "ABSTRACT_TEXT": "This study examines biomarkers.",
            "HAS_ABSTRACT": "True",
        }
        sample = record_to_sample(record)

        assert isinstance(sample, Sample)
        assert sample.id == "12345"
        assert "Biomarker study" in sample.input
        assert "This study examines biomarkers." in sample.input
        assert sample.metadata["fy"] == "2020"
        assert sample.metadata["ic"] == "CA"
        assert sample.metadata["ic_name"] == "NATIONAL CANCER INSTITUTE"
        assert sample.metadata["activity"] == "R01"
        assert sample.metadata["total_cost"] == "500000.0"
        assert sample.metadata["explicit_biomarker"] == "True"
        assert sample.metadata["has_abstract"] == "True"

    def test_calibration_format(self):
        """Calibration CSV row maps correctly to Sample."""
        record = {
            "YEAR": "2012",
            "APPLICATION_ID": "8303985",
            "ADMINISTERING_IC": "CA",
            "ACTIVITY": "R21",
            "TOTAL_COST": "264515.0",
            "PROJECT_TITLE": "Genome-wide DNA Methylation",
            "ABSTRACT": "This study identifies biomarkers for AML.",
            "MATCHED_TERMS": "pharmacodynamic biomarker",
        }
        sample = record_to_sample(record)

        assert isinstance(sample, Sample)
        assert sample.id == "8303985"
        assert "Genome-wide DNA Methylation" in sample.input
        assert "This study identifies biomarkers for AML." in sample.input
        assert sample.metadata["fy"] == "2012"
        assert sample.metadata["matched_terms"] == "pharmacodynamic biomarker"

    def test_missing_abstract(self):
        """Sample is created even when abstract is empty."""
        record = {
            "FY": "2005",
            "APPLICATION_ID": "99999",
            "PROJECT_TITLE": "Title only grant",
        }
        sample = record_to_sample(record)

        assert isinstance(sample, Sample)
        assert sample.id == "99999"
        assert "Title only grant" in sample.input
        # The abstract portion should be empty but the template still renders
        assert "**Title:**" in sample.input
        assert "**Abstract:**" in sample.input

    def test_input_template_matches_grader_prompt(self):
        """_INPUT_TEMPLATE in inspect_task.py is the same as USER_PROMPT_TEMPLATE."""
        assert _INPUT_TEMPLATE == USER_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Code enum counts
# ---------------------------------------------------------------------------


class TestCodeEnums:
    """Verify code enum sets match RUBRIC.md counts."""

    def test_dim1_count(self):
        """Dimension 1 has exactly 17 codes."""
        assert len(VALID_DIM1) == 17

    def test_dim2_count(self):
        """Dimension 2 has exactly 10 codes."""
        assert len(VALID_DIM2) == 10

    def test_dim3_count(self):
        """Dimension 3 has exactly 5 codes."""
        assert len(VALID_DIM3) == 5
