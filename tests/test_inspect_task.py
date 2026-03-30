"""Tests for the Inspect AI biomarker grading task."""

import json

from inspect_ai import Task
from inspect_ai.dataset import Sample

from inspect_task import (
    VALID_DIM1,
    VALID_DIM2,
    VALID_DIM3,
    _INPUT_TEMPLATE,
    _parse_classification,
    _validate_codes,
    biomarker_grading,
    record_to_sample,
    rubric_solver,
)
from scripts.grader_prompt import USER_PROMPT_TEMPLATE, build_system_prompt, load_rubric


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
        assert sample.metadata["explicit_biomarker"] is True
        assert sample.metadata["has_abstract"] is True

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
        # Calibration CSVs lack HAS_ABSTRACT — should fall back to bool(abstract.strip())
        assert sample.metadata["has_abstract"] is True
        # Calibration CSVs lack EXPLICIT_BIOMARKER — should default to False
        assert sample.metadata["explicit_biomarker"] is False

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
        # No HAS_ABSTRACT column and no abstract text → has_abstract is False
        assert sample.metadata["has_abstract"] is False
        # No EXPLICIT_BIOMARKER column → explicit_biomarker is False
        assert sample.metadata["explicit_biomarker"] is False

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


# ---------------------------------------------------------------------------
# Task 3: Solver tests
# ---------------------------------------------------------------------------


class TestRubricSolver:
    """Tests for the rubric solver."""

    def test_solver_is_callable(self):
        """rubric_solver() returns a callable Solver."""
        s = rubric_solver()
        assert callable(s)

    def test_system_prompt_contains_rubric_codes(self):
        """The built system prompt includes key rubric codes."""
        rubric_text = load_rubric()
        prompt = build_system_prompt(rubric_text)

        # Check a sampling of codes from each dimension
        assert "susceptibility_risk" in prompt
        assert "predictive_optimal" in prompt
        assert "methods_correlational" in prompt
        assert "observational_retrospective" in prompt
        assert "experimental_rct" in prompt
        assert "methods_secondary_analysis" in prompt
        assert "correlational" in prompt
        assert "causal_clinical" in prompt
        assert "methods_for_causal" in prompt

    def test_system_prompt_excludes_references(self):
        """The system prompt strips the References section."""
        rubric_text = load_rubric()
        prompt = build_system_prompt(rubric_text)
        assert "## References" not in prompt
        assert "FDA-NIH BEST" not in prompt or "SOURCE OF TRUTH" not in prompt


# ---------------------------------------------------------------------------
# Task 4: _parse_classification tests
# ---------------------------------------------------------------------------


class TestParseClassification:
    """Tests for the classification parser."""

    def test_valid_json(self):
        """Valid JSON parses correctly and includes validation result."""
        payload = {
            "biomarker_use": {
                "primary": "diagnostic",
                "secondary": None,
                "confidence": "high",
            },
            "research_design": {
                "primary": "observational_cohort",
                "secondary": None,
                "confidence": "medium",
            },
            "evidence_strength": {"code": "correlational", "confidence": "high"},
            "key_phrases": ["biomarker level"],
            "reasoning": "The study measures a diagnostic biomarker.",
        }
        raw = json.dumps(payload)
        result = _parse_classification(raw)

        assert result is not None
        assert result["biomarker_use"]["primary"] == "diagnostic"
        assert result["research_design"]["primary"] == "observational_cohort"
        assert result["evidence_strength"]["code"] == "correlational"
        assert result["valid"] is True
        assert result["invalid_codes"] == []

    def test_markdown_fenced_json(self):
        """JSON wrapped in markdown code fences parses correctly."""
        payload = {
            "biomarker_use": {"primary": "monitoring", "secondary": None, "confidence": "high"},
            "research_design": {"primary": "experimental_rct", "secondary": None, "confidence": "high"},
            "evidence_strength": {"code": "experimental_weak", "confidence": "medium"},
            "key_phrases": [],
            "reasoning": "RCT with monitoring biomarker.",
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = _parse_classification(raw)

        assert result is not None
        assert result["biomarker_use"]["primary"] == "monitoring"
        assert result["valid"] is True

    def test_bare_fenced_json(self):
        """JSON wrapped in bare ``` fences parses correctly."""
        payload = {
            "biomarker_use": {"primary": "safety", "secondary": None, "confidence": "low"},
            "research_design": {"primary": "experimental_singlearm", "secondary": None, "confidence": "low"},
            "evidence_strength": {"code": "correlational", "confidence": "low"},
            "key_phrases": [],
            "reasoning": "Safety biomarker in single-arm trial.",
        }
        raw = f"```\n{json.dumps(payload)}\n```"
        result = _parse_classification(raw)

        assert result is not None
        assert result["biomarker_use"]["primary"] == "safety"
        assert result["valid"] is True

    def test_malformed_json(self):
        """Malformed JSON returns None."""
        raw = "This is not JSON at all {broken"
        result = _parse_classification(raw)
        assert result is None

    def test_non_dict_json(self):
        """Valid JSON that is not a dict returns None."""
        result = _parse_classification("[1, 2, 3]")
        assert result is None

    def test_invalid_codes_reports_which_dimensions(self):
        """JSON with invalid codes parses but reports invalid dimensions."""
        payload = {
            "biomarker_use": {"primary": "not_a_real_code", "secondary": None, "confidence": "high"},
            "research_design": {"primary": "fake_design", "secondary": None, "confidence": "high"},
            "evidence_strength": {"code": "imaginary", "confidence": "high"},
            "key_phrases": [],
            "reasoning": "Made up codes.",
        }
        raw = json.dumps(payload)
        result = _parse_classification(raw)

        # Parsing succeeds but validation flags all three dimensions
        assert result is not None
        assert result["valid"] is False
        assert "dim1" in result["invalid_codes"]
        assert "dim2" in result["invalid_codes"]
        assert "dim3" in result["invalid_codes"]

    def test_validate_codes_valid(self):
        """Valid codes return an empty invalid list."""
        parsed = {
            "biomarker_use": {"primary": "predictive_optimal", "secondary": "pharmacodynamic"},
            "research_design": {"primary": "experimental_rct", "secondary": None},
            "evidence_strength": {"code": "causal_clinical"},
        }
        assert _validate_codes(parsed) == []

    def test_validate_codes_invalid_dim1(self):
        """Invalid dim1 code is reported."""
        parsed = {
            "biomarker_use": {"primary": "bogus_code"},
            "research_design": {"primary": "experimental_rct"},
            "evidence_strength": {"code": "correlational"},
        }
        result = _validate_codes(parsed)
        assert "dim1" in result
        assert "dim2" not in result
        assert "dim3" not in result

    def test_validate_codes_invalid_dim2(self):
        """Invalid dim2 code is reported."""
        parsed = {
            "biomarker_use": {"primary": "diagnostic"},
            "research_design": {"primary": "not_a_design"},
            "evidence_strength": {"code": "correlational"},
        }
        result = _validate_codes(parsed)
        assert "dim2" in result
        assert "dim1" not in result

    def test_validate_codes_invalid_dim3(self):
        """Invalid dim3 code is reported."""
        parsed = {
            "biomarker_use": {"primary": "diagnostic"},
            "research_design": {"primary": "experimental_rct"},
            "evidence_strength": {"code": "not_real"},
        }
        result = _validate_codes(parsed)
        assert "dim3" in result
        assert "dim1" not in result
        assert "dim2" not in result

    def test_validate_codes_invalid_secondary(self):
        """Invalid secondary code is reported for dim1."""
        parsed = {
            "biomarker_use": {"primary": "diagnostic", "secondary": "fake_secondary"},
            "research_design": {"primary": "experimental_rct"},
            "evidence_strength": {"code": "correlational"},
        }
        result = _validate_codes(parsed)
        assert "dim1" in result


# ---------------------------------------------------------------------------
# Task 5: Task definition tests
# ---------------------------------------------------------------------------


class TestBiomarkerGrading:
    """Tests for the task definition."""

    def test_returns_task_instance(self):
        """biomarker_grading() returns a Task."""
        t = biomarker_grading()
        assert isinstance(t, Task)

    def test_task_has_solver(self):
        """The task has a solver list."""
        t = biomarker_grading()
        assert t.solver is not None

    def test_task_has_scorer(self):
        """The task has a scorer."""
        t = biomarker_grading()
        assert t.scorer is not None

    def test_task_config(self):
        """The task has the expected GenerateConfig."""
        t = biomarker_grading()
        assert t.config.temperature == 0.1
        assert t.config.max_tokens == 500
