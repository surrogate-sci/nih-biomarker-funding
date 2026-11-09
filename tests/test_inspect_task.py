"""Tests for the Inspect AI biomarker grading task."""

import json
import unittest

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
    parse_rubric_codes,
    record_to_sample,
    rubric_solver,
)
from scripts.grader_prompt import USER_PROMPT_TEMPLATE, build_system_prompt, load_rubric


# ---------------------------------------------------------------------------
# Task 2: record_to_sample tests
# ---------------------------------------------------------------------------


class TestRecordToSample(unittest.TestCase):
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

        self.assertIsInstance(sample, Sample)
        self.assertEqual(sample.id, "12345")
        self.assertIn("Biomarker study", sample.input)
        self.assertIn("This study examines biomarkers.", sample.input)
        self.assertEqual(sample.metadata["fy"], "2020")
        self.assertEqual(sample.metadata["ic"], "CA")
        self.assertEqual(sample.metadata["ic_name"], "NATIONAL CANCER INSTITUTE")
        self.assertEqual(sample.metadata["activity"], "R01")
        self.assertEqual(sample.metadata["total_cost"], "500000.0")
        self.assertTrue(sample.metadata["explicit_biomarker"])
        self.assertTrue(sample.metadata["has_abstract"])

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

        self.assertIsInstance(sample, Sample)
        self.assertEqual(sample.id, "8303985")
        self.assertIn("Genome-wide DNA Methylation", sample.input)
        self.assertIn("This study identifies biomarkers for AML.", sample.input)
        self.assertEqual(sample.metadata["fy"], "2012")
        self.assertEqual(sample.metadata["matched_terms"], "pharmacodynamic biomarker")
        # Calibration CSVs lack HAS_ABSTRACT — should fall back to bool(abstract.strip())
        self.assertTrue(sample.metadata["has_abstract"])
        # Calibration CSVs lack EXPLICIT_BIOMARKER — should default to False
        self.assertFalse(sample.metadata["explicit_biomarker"])

    def test_missing_abstract(self):
        """Sample is created even when abstract is empty."""
        record = {
            "FY": "2005",
            "APPLICATION_ID": "99999",
            "PROJECT_TITLE": "Title only grant",
        }
        sample = record_to_sample(record)

        self.assertIsInstance(sample, Sample)
        self.assertEqual(sample.id, "99999")
        self.assertIn("Title only grant", sample.input)
        # The abstract portion should be empty but the template still renders
        self.assertIn("**Title:**", sample.input)
        self.assertIn("**Abstract:**", sample.input)
        # No HAS_ABSTRACT column and no abstract text → has_abstract is False
        self.assertFalse(sample.metadata["has_abstract"])
        # No EXPLICIT_BIOMARKER column → explicit_biomarker is False
        self.assertFalse(sample.metadata["explicit_biomarker"])

    def test_input_template_matches_grader_prompt(self):
        """_INPUT_TEMPLATE in inspect_task.py is the same as USER_PROMPT_TEMPLATE."""
        self.assertEqual(_INPUT_TEMPLATE, USER_PROMPT_TEMPLATE)

    def test_gold_labels_set_target(self):
        """When GOLD_DIM* columns are present, Sample.target is set."""
        record = {
            "FY": "2020",
            "APPLICATION_ID": "12345",
            "PROJECT_TITLE": "Test grant",
            "ABSTRACT_TEXT": "Abstract.",
            "GOLD_DIM1": "diagnostic",
            "GOLD_DIM2": "observational_cohort",
            "GOLD_DIM3": "correlational",
        }
        sample = record_to_sample(record)
        self.assertIsNotNone(sample.target)
        target = json.loads(sample.target)
        self.assertEqual(target["dim1"], "diagnostic")
        self.assertEqual(target["dim2"], "observational_cohort")
        self.assertEqual(target["dim3"], "correlational")

    def test_no_gold_labels_target_is_empty(self):
        """Without GOLD_DIM* columns, Sample.target is empty string."""
        record = {
            "FY": "2020",
            "APPLICATION_ID": "12345",
            "PROJECT_TITLE": "Test grant",
            "ABSTRACT_TEXT": "Abstract.",
        }
        sample = record_to_sample(record)
        self.assertEqual(sample.target, "")

    def test_partial_gold_labels(self):
        """Partial gold labels (only some dimensions) still set target."""
        record = {
            "FY": "2020",
            "APPLICATION_ID": "12345",
            "PROJECT_TITLE": "Test grant",
            "ABSTRACT_TEXT": "Abstract.",
            "GOLD_DIM1": "diagnostic",
        }
        sample = record_to_sample(record)
        self.assertIsNotNone(sample.target)
        target = json.loads(sample.target)
        self.assertEqual(target["dim1"], "diagnostic")
        self.assertNotIn("dim2", target)
        self.assertNotIn("dim3", target)


# ---------------------------------------------------------------------------
# Code enum counts
# ---------------------------------------------------------------------------


class TestCodeEnums(unittest.TestCase):
    """Verify code enum sets match RUBRIC.md counts."""

    def test_dim1_count(self):
        """Dimension 1 has exactly 22 codes (incl. assay_technology_unspecified)."""
        self.assertEqual(len(VALID_DIM1), 22)
        self.assertIn("assay_technology_unspecified", VALID_DIM1)

    def test_dim2_count(self):
        """Dimension 2 has exactly 10 codes."""
        self.assertEqual(len(VALID_DIM2), 10)

    def test_dim3_count(self):
        """Dimension 3 has exactly 5 codes."""
        self.assertEqual(len(VALID_DIM3), 5)

    def test_parse_rubric_codes_returns_three_dimensions(self):
        """parse_rubric_codes returns codes for dimensions 1, 2, and 3."""
        codes = parse_rubric_codes()
        self.assertEqual(set(codes.keys()), {1, 2, 3})

    def test_parsed_codes_match_module_level_sets(self):
        """Module-level VALID_DIM* sets match what parse_rubric_codes returns."""
        codes = parse_rubric_codes()
        self.assertEqual(codes[1], VALID_DIM1)
        self.assertEqual(codes[2], VALID_DIM2)
        self.assertEqual(codes[3], VALID_DIM3)

    def test_specific_codes_present(self):
        """Spot-check that well-known codes are present in each dimension."""
        self.assertIn("diagnostic", VALID_DIM1)
        self.assertIn("surrogate_endpoint", VALID_DIM1)
        self.assertIn("methods_causal", VALID_DIM1)
        self.assertIn("experimental_rct", VALID_DIM2)
        self.assertIn("observational_cohort", VALID_DIM2)
        self.assertIn("correlational", VALID_DIM3)
        self.assertIn("causal_clinical", VALID_DIM3)


# ---------------------------------------------------------------------------
# Task 3: Solver tests
# ---------------------------------------------------------------------------


class TestRubricSolver(unittest.TestCase):
    """Tests for the rubric solver."""

    def test_solver_is_callable(self):
        """rubric_solver() returns a callable Solver."""
        s = rubric_solver()
        self.assertTrue(callable(s))

    def test_system_prompt_contains_rubric_codes(self):
        """The built system prompt includes key rubric codes."""
        rubric_text = load_rubric()
        prompt = build_system_prompt(rubric_text)

        # Check a sampling of codes from each dimension
        self.assertIn("susceptibility_risk", prompt)
        self.assertIn("predictive_optimal", prompt)
        self.assertIn("methods_correlational", prompt)
        self.assertIn("observational_retrospective", prompt)
        self.assertIn("experimental_rct", prompt)
        self.assertIn("methods_secondary_analysis", prompt)
        self.assertIn("correlational", prompt)
        self.assertIn("causal_clinical", prompt)
        self.assertIn("methods_for_causal", prompt)

    def test_system_prompt_excludes_references(self):
        """The system prompt strips the References section."""
        rubric_text = load_rubric()
        prompt = build_system_prompt(rubric_text)
        self.assertNotIn("## References", prompt)
        self.assertTrue("FDA-NIH BEST" not in prompt or "SOURCE OF TRUTH" not in prompt)


# ---------------------------------------------------------------------------
# Task 4: _parse_classification tests
# ---------------------------------------------------------------------------


class TestParseClassification(unittest.TestCase):
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

        self.assertIsNotNone(result)
        self.assertEqual(result["biomarker_use"]["primary"], "diagnostic")
        self.assertEqual(result["research_design"]["primary"], "observational_cohort")
        self.assertEqual(result["evidence_strength"]["code"], "correlational")
        self.assertTrue(result["valid"])
        self.assertEqual(result["invalid_codes"], [])

    def test_markdown_fenced_json(self):
        """JSON wrapped in markdown code fences parses correctly."""
        payload = {
            "biomarker_use": {
                "primary": "monitoring",
                "secondary": None,
                "confidence": "high",
            },
            "research_design": {
                "primary": "experimental_rct",
                "secondary": None,
                "confidence": "high",
            },
            "evidence_strength": {"code": "experimental_weak", "confidence": "medium"},
            "key_phrases": [],
            "reasoning": "RCT with monitoring biomarker.",
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = _parse_classification(raw)

        self.assertIsNotNone(result)
        self.assertEqual(result["biomarker_use"]["primary"], "monitoring")
        self.assertTrue(result["valid"])

    def test_bare_fenced_json(self):
        """JSON wrapped in bare ``` fences parses correctly."""
        payload = {
            "biomarker_use": {
                "primary": "safety",
                "secondary": None,
                "confidence": "low",
            },
            "research_design": {
                "primary": "experimental_singlearm",
                "secondary": None,
                "confidence": "low",
            },
            "evidence_strength": {"code": "correlational", "confidence": "low"},
            "key_phrases": [],
            "reasoning": "Safety biomarker in single-arm trial.",
        }
        raw = f"```\n{json.dumps(payload)}\n```"
        result = _parse_classification(raw)

        self.assertIsNotNone(result)
        self.assertEqual(result["biomarker_use"]["primary"], "safety")
        self.assertTrue(result["valid"])

    def test_malformed_json(self):
        """Malformed JSON returns None."""
        raw = "This is not JSON at all {broken"
        result = _parse_classification(raw)
        self.assertIsNone(result)

    def test_non_dict_json(self):
        """Valid JSON that is not a dict returns None."""
        result = _parse_classification("[1, 2, 3]")
        self.assertIsNone(result)

    def test_invalid_codes_reports_which_dimensions(self):
        """JSON with invalid codes parses but reports invalid dimensions."""
        payload = {
            "biomarker_use": {
                "primary": "not_a_real_code",
                "secondary": None,
                "confidence": "high",
            },
            "research_design": {
                "primary": "fake_design",
                "secondary": None,
                "confidence": "high",
            },
            "evidence_strength": {"code": "imaginary", "confidence": "high"},
            "key_phrases": [],
            "reasoning": "Made up codes.",
        }
        raw = json.dumps(payload)
        result = _parse_classification(raw)

        # Parsing succeeds but validation flags all three dimensions
        self.assertIsNotNone(result)
        self.assertFalse(result["valid"])
        self.assertIn("dim1", result["invalid_codes"])
        self.assertIn("dim2", result["invalid_codes"])
        self.assertIn("dim3", result["invalid_codes"])

    def test_validate_codes_valid(self):
        """Valid codes return an empty invalid list."""
        parsed = {
            "biomarker_use": {
                "primary": "predictive_optimal",
                "secondary": "pharmacodynamic",
            },
            "research_design": {"primary": "experimental_rct", "secondary": None},
            "evidence_strength": {"code": "causal_clinical"},
        }
        self.assertEqual(_validate_codes(parsed), [])

    def test_validate_codes_invalid_dim1(self):
        """Invalid dim1 code is reported."""
        parsed = {
            "biomarker_use": {"primary": "bogus_code"},
            "research_design": {"primary": "experimental_rct"},
            "evidence_strength": {"code": "correlational"},
        }
        result = _validate_codes(parsed)
        self.assertIn("dim1", result)
        self.assertNotIn("dim2", result)
        self.assertNotIn("dim3", result)

    def test_validate_codes_invalid_dim2(self):
        """Invalid dim2 code is reported."""
        parsed = {
            "biomarker_use": {"primary": "diagnostic"},
            "research_design": {"primary": "not_a_design"},
            "evidence_strength": {"code": "correlational"},
        }
        result = _validate_codes(parsed)
        self.assertIn("dim2", result)
        self.assertNotIn("dim1", result)

    def test_validate_codes_invalid_dim3(self):
        """Invalid dim3 code is reported."""
        parsed = {
            "biomarker_use": {"primary": "diagnostic"},
            "research_design": {"primary": "experimental_rct"},
            "evidence_strength": {"code": "not_real"},
        }
        result = _validate_codes(parsed)
        self.assertIn("dim3", result)
        self.assertNotIn("dim1", result)
        self.assertNotIn("dim2", result)

    def test_validate_codes_invalid_secondary(self):
        """Invalid secondary code is reported for dim1."""
        parsed = {
            "biomarker_use": {"primary": "diagnostic", "secondary": "fake_secondary"},
            "research_design": {"primary": "experimental_rct"},
            "evidence_strength": {"code": "correlational"},
        }
        result = _validate_codes(parsed)
        self.assertIn("dim1", result)

    def test_step0_exit_codes_allow_null_dim2_dim3(self):
        """not_applicable and disease_non_biomarker accept null Dim2/Dim3 (incl. JSON null objects)."""
        for code in ("not_applicable", "disease_non_biomarker"):
            parsed = {
                "biomarker_use": {"primary": code, "secondary": "null"},
                "research_design": None,
                "evidence_strength": {"code": None},
            }
            self.assertEqual(_validate_codes(parsed), [], code)

    def test_biomarker_code_still_requires_dim2_dim3(self):
        """A substantive biomarker code with null Dim2/Dim3 is invalid."""
        parsed = {
            "biomarker_use": {"primary": "assay_technology_unspecified"},
            "research_design": None,
            "evidence_strength": None,
        }
        self.assertEqual(_validate_codes(parsed), ["dim2", "dim3"])

    def test_parse_json_trailing_comma(self):
        """A trailing comma before the closing brace (seen from Sonnet 5.5) still parses."""
        raw = (
            '{"biomarker_use": {"primary": "diagnostic"}, '
            '"research_design": {"primary": "experimental_rct"}, '
            '"evidence_strength": {"code": "correlational"}, "reasoning": "x", }'
        )
        result = _parse_classification(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result["valid"])

    def test_crosssectional_separator_variants_are_aliased(self):
        """Observed spellings map to observational_crosssectional; others stay invalid."""
        for variant in (
            "observational_cross-sectional",
            "observational_cross_sectional",
            "observational_cross_sectional_placeholder",
            "observational_cross-sectional_placeholder",
            "observational_cross_sectional_placeholder_removed",
        ):
            raw = json.dumps(
                {
                    "biomarker_use": {"primary": "diagnostic"},
                    "research_design": {
                        "primary": "experimental_rct",
                        "secondary": variant,
                    },
                    "evidence_strength": {"code": "correlational"},
                }
            )
            result = _parse_classification(raw)
            self.assertTrue(result["valid"], variant)
            self.assertEqual(
                result["research_design"]["secondary"], "observational_crosssectional"
            )
            self.assertEqual(len(result["code_aliases_applied"]), 1)
        raw = json.dumps(
            {
                "biomarker_use": {"primary": "diagnostic"},
                "research_design": {"primary": "observational_cohort_placeholder"},
                "evidence_strength": {"code": "correlational"},
            }
        )
        self.assertFalse(_parse_classification(raw)["valid"])

    def test_parse_json_self_correction_takes_last_object(self):
        """Sonnet 5.5 sometimes emits a JSON, then 'Correction: ... Corrected JSON:' and a second one."""
        bad = {
            "biomarker_use": {"primary": "diagnostic"},
            "research_design": {"primary": "observational_cohort_placeholder"},
            "evidence_strength": {"code": "correlational"},
        }
        good = {**bad, "research_design": {"primary": "observational_crosssectional"}}
        raw = f"{json.dumps(bad)}\n\nCorrection: use a defined code. Corrected JSON:\n\n{json.dumps(good)}"
        result = _parse_classification(raw)
        self.assertTrue(result["valid"])
        self.assertEqual(
            result["research_design"]["primary"], "observational_crosssectional"
        )

    def test_truncated_response_is_parse_failure(self):
        """A cut-off answer must not return a nested inner object (reviewer #1)."""
        raw = (
            '{"biomarker_use": {"primary": "diagnostic"}, '
            '"research_design": {"primary": "experimental_rct"}, '
            '"evidence_strength": {"code": "corr'
        )
        self.assertIsNone(_parse_classification(raw))

    def test_stray_object_after_answer_is_ignored(self):
        """A later non-classification object or an echoed schema template does not win."""
        answer = json.dumps(
            {
                "biomarker_use": {"primary": "diagnostic"},
                "research_design": {"primary": "experimental_rct"},
                "evidence_strength": {"code": "correlational"},
            }
        )
        for tail in (
            '\nNote: e.g. {"primary": "prognostic_risk"}',
            '\nSchema was: {"biomarker_use": {"primary": "<code from Dimension 1>"}}',
        ):
            result = _parse_classification(answer + tail)
            self.assertEqual(result["biomarker_use"]["primary"], "diagnostic", tail)

    def test_trailing_comma_inside_string_is_preserved(self):
        """Comma cleanup must not alter quoted text (key_phrases must stay exact)."""
        raw = (
            '{"biomarker_use": {"primary": "diagnostic"}, '
            '"research_design": {"primary": "experimental_rct"}, '
            '"evidence_strength": {"code": "correlational"}, '
            '"key_phrases": ["uses [a, ] and x, }"], }'
        )
        result = _parse_classification(raw)
        self.assertEqual(result["key_phrases"], ["uses [a, ] and x, }"])

    def test_non_dict_dimension_is_invalid_not_error(self):
        """A bare string where an object is expected is an invalid code, not a crash."""
        raw = json.dumps(
            {
                "biomarker_use": "diagnostic",
                "research_design": {"primary": "experimental_rct"},
                "evidence_strength": {"code": "correlational"},
            }
        )
        result = _parse_classification(raw)
        self.assertFalse(result["valid"])
        self.assertIn("dim1", result["invalid_codes"])

    def test_parse_json_with_surrounding_prose(self):
        """Unfenced JSON surrounded by prose still parses."""
        raw = (
            'Here is the classification:\n{"biomarker_use": {"primary": "diagnostic"}, '
            '"research_design": {"primary": "experimental_rct"}, '
            '"evidence_strength": {"code": "correlational"}}\nDone.'
        )
        result = _parse_classification(raw)
        self.assertIsNotNone(result)
        self.assertTrue(result["valid"])


# ---------------------------------------------------------------------------
# Task 5: Task definition tests
# ---------------------------------------------------------------------------


class TestBiomarkerGrading(unittest.TestCase):
    """Tests for the task definition."""

    def test_returns_task_instance(self):
        """biomarker_grading() returns a Task."""
        t = biomarker_grading()
        self.assertIsInstance(t, Task)

    def test_task_has_solver(self):
        """The task has a solver list."""
        t = biomarker_grading()
        self.assertIsNotNone(t.solver)

    def test_task_has_scorer(self):
        """The task has a scorer."""
        t = biomarker_grading()
        self.assertIsNotNone(t.scorer)

    def test_task_config_no_hardcoded_defaults(self):
        """The task does not hardcode temperature or max_tokens."""
        t = biomarker_grading()
        # These should be None (CLI-controlled), not hardcoded values
        self.assertIsNone(t.config.temperature)
        self.assertIsNone(t.config.max_tokens)


if __name__ == "__main__":
    unittest.main()
