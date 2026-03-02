"""
NIH Biomarker Project Grader Prompt and Test Script

Uses OpenRouter API to compare Gemini 1.5 Flash vs GPT-4o-mini
"""

import json
from pathlib import Path

# JSON Schema for validation
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["biomarker_use", "research_design", "evidence_strength", "key_phrases", "reasoning"],
    "properties": {
        "biomarker_use": {
            "type": "object",
            "required": ["primary", "confidence"],
            "properties": {
                "primary": {
                    "type": "string",
                    "enum": [
                        "susceptibility_risk", "diagnostic", "monitoring",
                        "prognostic_risk", "prognostic_efficacy", "prognostic_enrichment",
                        "predictive_optimal", "predictive_enrichment", "predictive_ambiguous",
                        "pharmacodynamic", "safety", "surrogate_endpoint",
                        "stratification_treatment", "stratification_diagnostic",
                        "stratification_ambiguous", "methods_causal", "methods_correlational"
                    ]
                },
                "secondary": {"type": ["string", "null"]},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            }
        },
        "research_design": {
            "type": "object",
            "required": ["primary", "confidence"],
            "properties": {
                "primary": {
                    "type": "string",
                    "enum": [
                        "observational_retrospective", "observational_crosssectional",
                        "observational_cohort", "observational_longitudinal",
                        "observational_case_cohort", "observational_quasi",
                        "experimental_singlearm", "experimental_rct", "experimental_perturbation",
                        "methods_secondary_analysis"
                    ]
                },
                "secondary": {"type": ["string", "null"]},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            }
        },
        "evidence_strength": {
            "type": "object",
            "required": ["code", "confidence"],
            "properties": {
                "code": {
                    "type": "string",
                    "enum": [
                        "correlational", "experimental_weak", "causal_preclinical",
                        "causal_clinical", "methods_for_causal"
                    ]
                },
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            }
        },
        "key_phrases": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 5
        },
        "reasoning": {"type": "string", "maxLength": 500}
    }
}


# ---------------------------------------------------------------------------
# Rubric loading and system prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PREAMBLE = (
    "You are an expert biomedical research methodologist classifying "
    "NIH-funded biomarker research projects.\n\n"
    "Your task is to classify each project on THREE dimensions based on "
    "the title and abstract."
)

_SYSTEM_PROMPT_OUTPUT_FORMAT = """
## Output Format

You MUST respond with valid JSON matching this exact schema:

```json
{
  "biomarker_use": {
    "primary": "<code from Dimension 1>",
    "secondary": "<code from Dimension 1 or null>",
    "confidence": "<high|medium|low>"
  },
  "research_design": {
    "primary": "<code from Dimension 2>",
    "secondary": "<code from Dimension 2 or null>",
    "confidence": "<high|medium|low>"
  },
  "evidence_strength": {
    "code": "<code from Dimension 3>",
    "confidence": "<high|medium|low>"
  },
  "key_phrases": [
    "<exact quote from abstract supporting biomarker_use classification>",
    "<exact quote from abstract supporting research_design classification>",
    "<exact quote from abstract supporting evidence_strength classification>"
  ],
  "reasoning": "<1-2 sentences explaining the classification>"
}
```

IMPORTANT:
- Use ONLY codes defined in the rubric above
- key_phrases must be EXACT quotes from the abstract
- If uncertain between categories, use the more conservative code (correlational > causal, prognostic_risk > prognostic_efficacy, predictive_ambiguous > predictive_enrichment > predictive_optimal)
"""


def load_rubric(path: Path | None = None) -> str:
    """Read the classification rubric from data/RUBRIC.md.

    Parameters
    ----------
    path : Path or None
        Explicit path to the rubric file. When *None* (the default), the path
        is resolved relative to this script's location:
        ``<repo>/data/RUBRIC.md``.

    Returns
    -------
    str
        The full text content of the rubric file.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "RUBRIC.md"
    return Path(path).read_text(encoding="utf-8")


def build_system_prompt(rubric_text: str) -> str:
    """Construct the full system prompt from rubric text.

    The prompt is assembled from three pieces:
    1. A preamble describing the classifier's role.
    2. The rubric text (loaded from ``data/RUBRIC.md``).
    3. Output-format instructions and classification rules.
    """
    return (
        f"{_SYSTEM_PROMPT_PREAMBLE}\n\n"
        f"{rubric_text}\n"
        f"{_SYSTEM_PROMPT_OUTPUT_FORMAT}"
    )


# ---------------------------------------------------------------------------
# Legacy system prompt -- kept for reference only.  Do NOT use in production.
# ---------------------------------------------------------------------------

_LEGACY_SYSTEM_PROMPT = """You are an expert biomedical research methodologist classifying NIH-funded biomarker research projects.

Your task is to classify each project on THREE dimensions based on the title and abstract.

## Dimension 1: Intended Biomarker Use (FDA BEST framework + extensions)

| Code | Definition |
|------|------------|
| susceptibility_risk | Indicates potential for developing disease |
| diagnostic | Detects/confirms presence of disease |
| monitoring | Assesses disease status over time |
| prognostic | Predicts outcome regardless of treatment |
| risk | Predicts risk of developing disease or clinical outcomes |
| predictive | Predicts response to treatment; differentiates treatment vs placebo or active comparator |
| predictive_nonspecific | Claims "response to therapy" without specifying treatment; fails to distinguish from prognostic |
| pharmacodynamic | Measures biological response to drug exposure |
| safety | Measures toxicity or adverse events |
| surrogate_endpoint | Substitute for clinical endpoint (regulatory context) |
| stratification_treatment | Assigns patients to different treatments |
| stratification_diagnostic | Classifies disease subtypes for prognosis/natural history |
| stratification_ambiguous | Mentions stratification without clarifying treatment vs diagnostic purpose |
| methods_causal | Develops methods for causal inference, surrogate validation, treatment effect estimation |
| methods_correlational | Develops methods for association, prediction, classification (not causal) |

## Dimension 2: Research Design

| Code | Definition |
|------|------------|
| observational_retrospective | Chart review, biobank analysis, registry data |
| observational_crosssectional | Single timepoint association study |
| observational_cohort | Prospective follow-up of exposed vs unexposed groups |
| observational_longitudinal | Repeated measures over time, primarily descriptive |
| observational_case_cohort | Nested case-control or efficient sampling within cohort |
| observational_quasi | Exploits natural variation (policy change, instrumental variable, regression discontinuity) |
| experimental_singlearm | Pre/post without control group |
| experimental_rct | Randomized controlled trial |
| experimental_perturbation | Knockdown, drug exposure, dose-response (may lack full causal design) |
| methods_statistical | Developing analytic methods, not primary data collection |

## Dimension 3: Evidence Strength for BIOMARKER VALIDITY

CRITICAL: This rates evidence that the BIOMARKER ITSELF is causally valid - NOT whether the treatment effect is causal.

| Code | Definition |
|------|------------|
| correlational | Association only; biomarker correlates with outcome but no causal validation |
| experimental_weak | Intervention exists but BIOMARKER'S causal role not validated (e.g., biomarker measured in single RCT but not validated as surrogate) |
| causal_preclinical | Biomarker mechanism validated in vitro/animal models |
| causal_clinical | Biomarker validated via: causal surrogacy criteria, meta-analysis of multiple RCTs, biomarker-guided/adaptive trial designs, causal mediation within RCT/quasi-experiment; for risk biomarkers: counterfactual risk prediction or causal transportability analysis |
| methods_for_causal | Develops methods that ENABLE biomarker causal validation |

KEY DISTINCTION - RCT ≠ biomarker validation:
- "Single RCT measuring brain atrophy as pharmacodynamic marker" → experimental_weak (biomarker measured but not validated)
- "Biomarker-guided adaptive trial design" → causal_clinical (biomarker drives treatment decisions)
- "Meta-analysis across multiple RCTs validating surrogate" → causal_clinical
- "Longitudinal study finding biomarker predicts outcome" → correlational (association only)

## Key Distinctions

**Predictive vs Prognostic:**
- Prognostic: "Biomarker X predicts survival" (outcome regardless of treatment)
- Predictive: "Biomarker X predicts response to Drug Y" (treatment-biomarker interaction with named drug)
- Predictive_nonspecific: "predicts response to therapy" without specifying treatment

**Stratification:**
- Treatment: "Stratify patients to receive Drug A vs Drug B"
- Diagnostic: "Stratify disease subtypes for natural history"
- Ambiguous: "Stratify for improved outcomes" (unclear purpose)

**Methods Research:**
- methods_causal: Develops causal inference frameworks - THIS IS STRONG EVIDENCE for rigorous biomarker science
- methods_correlational: Develops prediction/classification methods

## Output Format

You MUST respond with valid JSON matching this exact schema:

```json
{
  "biomarker_use": {
    "primary": "<code from Dimension 1>",
    "secondary": "<code from Dimension 1 or null>",
    "confidence": "<high|medium|low>"
  },
  "research_design": {
    "primary": "<code from Dimension 2>",
    "secondary": "<code from Dimension 2 or null>",
    "confidence": "<high|medium|low>"
  },
  "evidence_strength": {
    "code": "<code from Dimension 3>",
    "confidence": "<high|medium|low>"
  },
  "key_phrases": [
    "<exact quote from abstract supporting biomarker_use classification>",
    "<exact quote from abstract supporting research_design classification>",
    "<exact quote from abstract supporting evidence_strength classification>"
  ],
  "reasoning": "<1-2 sentences explaining the classification>"
}
```

IMPORTANT:
- Use ONLY codes from the tables above
- key_phrases must be EXACT quotes from the abstract
- If uncertain between categories, use the more conservative (correlational > causal, prognostic > predictive)
"""


# ---------------------------------------------------------------------------
# Prompt templates and construction
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """Classify this NIH biomarker research project:

**Title:** {title}

**Abstract:** {abstract}

Return ONLY the JSON classification."""


def create_grading_prompt(title: str, abstract: str) -> list:
    """Create the messages for the grading API call"""
    system_prompt = build_system_prompt(load_rubric())
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(title=title, abstract=abstract)}
    ]


def test_grader():
    """Test the grader with example projects"""

    # Example projects for testing
    test_cases = [
        {
            "name": "Causal Methods Development",
            "title": "Statistical Methods for Cancer Biomarkers",
            "abstract": """This application is concerned with developing, evaluating and applying statistical methods
            for data that involves biomarkers. The second aim is concerned with clinical trials where the biomarker
            is to be used to evaluate a therapy as a surrogate endpoint. Because of the nature of the scientific
            question causal modeling is very natural in this context. We propose to develop both potential outcomes
            and structural causal models. We will investigate both single trial and multi trial settings with
            different endpoint types.""",
            "expected": {
                "biomarker_use": {"primary": "methods_causal"},
                "research_design": {"primary": "methods_statistical"},
                "evidence_strength": {"code": "methods_for_causal"}
            }
        },
        {
            "name": "Non-specific Predictive",
            "title": "Circulating Tumor Cell Capture & Analysis in a Multi-Center Prostate Cancer Trial",
            "abstract": """Prostate cancer is the most common malignancy and the second highest cause of cancer
            mortality in American men. New prognostic and predictive biomarkers are urgently needed to better
            inform our treatment decisions. Recent studies have demonstrated that quantification of peripheral
            blood circulating tumor cells (CTCs) predicts response to therapy and overall survival in advanced
            prostate cancer. It is our hypothesis that quantification and characterization of CTC can determine
            prognosis and predict response to therapy early in the course of the therapeutic regimen.""",
            "expected": {
                "biomarker_use": {"primary": "predictive_ambiguous"},
                "research_design": {"primary": "observational_cohort"},
                "evidence_strength": {"code": "correlational"}
            }
        },
        {
            "name": "Pharmacodynamic in RCT",
            "title": "Prospective Neuroimaging in Huntington's Disease",
            "abstract": """The most important goal of experimental therapeutics for symptomatic Huntington's disease (HD)
            is to develop disease-modifying (neuroprotective) therapies able to slow progression. We used these
            tools as a pharmacodynamic biomarker in a pilot study of high-dose Creatine, a leading candidate
            neuroprotective agent, in HD subjects. We found that high dose Creatine slowed brain atrophy, reduced
            measures of oxidative stress. We are seeking to validate our neuro-imaging tools in a funded
            placebo-controlled, double-blind Phase III clinical trial of high-dose creatine as a biomarker of
            disease progression.""",
            "expected": {
                "biomarker_use": {"primary": "pharmacodynamic"},
                "research_design": {"primary": "experimental_rct"},
                "evidence_strength": {"code": "experimental_weak"}  # imaging as PD without mechanistic validation
            }
        },
        {
            "name": "Surrogate Endpoint in RCT",
            "title": "The effects of randomized, low-dose hormone therapy on mammographic density",
            "abstract": """The proposed ancillary study will efficiently examine the effects of randomized low-dose HT
            on key breast cancer surrogate endpoints: mammographic density and rates of abnormal mammograms.
            In KEEPS, a total of 720 women were randomized to oral conjugated equine estrogens, transdermal
            17-beta estradiol, or placebo. We will determine if these two low-dose HT regimens are associated
            with change in mammographic density.""",
            "expected": {
                "biomarker_use": {"primary": "surrogate_endpoint"},
                "research_design": {"primary": "experimental_rct"},
                "evidence_strength": {"code": "experimental_weak"}  # density as surrogate without causal validation
            }
        },
        {
            "name": "Risk Prediction - Correlational",
            "title": "Improving Cardiovascular Risk Prediction with Novel Biomarkers",
            "abstract": """Cardiovascular disease (CVD) remains the leading cause of death in the United States.
            Current risk prediction models like the Pooled Cohort Equations have limited accuracy, particularly
            in diverse populations. This prospective cohort study will evaluate whether adding novel inflammatory
            biomarkers (high-sensitivity CRP, IL-6, fibrinogen) to traditional risk factors improves CVD risk
            prediction. We will assess discrimination using C-statistics and calibration using observed/expected
            ratios in 15,000 participants followed for 10 years. External validation will be performed in two
            independent cohorts to assess generalizability.""",
            "expected": {
                "biomarker_use": {"primary": "susceptibility_risk"},
                "research_design": {"primary": "observational_cohort"},
                "evidence_strength": {"code": "correlational"}  # risk prediction without causal validation
            }
        },
        {
            "name": "Risk Prediction - Causal Transportability",
            "title": "Causal Transportability of Polygenic Risk Scores Across Populations",
            "abstract": """Polygenic risk scores (PRS) for coronary heart disease show variable performance across
            ancestral populations, raising concerns about health equity. This project develops causal transportability
            methods to understand when and why PRS predictions fail to generalize. Using data from UK Biobank,
            Million Veteran Program, and All of Us, we will: (1) apply causal selection diagrams to identify
            sources of transportability failure; (2) develop counterfactual recalibration methods that adjust for
            differences in effect modification and confounding across populations; (3) validate transported PRS
            in held-out populations using both discrimination and decision-theoretic calibration metrics. Our
            framework extends beyond simple recalibration to address the causal structure underlying prediction
            model transportability.""",
            "expected": {
                "biomarker_use": {"primary": "susceptibility_risk"},
                "research_design": {"primary": "observational_cohort"},
                "evidence_strength": {"code": "causal_clinical"}  # causal transportability analysis
            }
        }
    ]

    return test_cases


# API call functions
def call_openrouter(messages: list, model: str, api_key: str) -> dict:
    """Call OpenRouter API"""
    import urllib.request

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,  # Low temp for consistency
        "max_tokens": 500
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/nih-biomarker-funding",
            "X-Title": "NIH Biomarker Grader"
        }
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())

    return result


def call_openai(messages: list, model: str, api_key: str) -> dict:
    """Call OpenAI API directly"""
    import urllib.request

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 500
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())

    return result


def run_comparison(openrouter_key: str = None, openai_key: str = None):
    """Run comparison between Gemini Flash and GPT-4o-mini"""
    import os

    # Model configurations
    models = {}

    if openrouter_key:
        models["gemini-flash"] = {
            "id": "google/gemini-2.0-flash-001",
            "api": "openrouter",
            "key": openrouter_key
        }

    if openai_key:
        models["gpt4o-mini"] = {
            "id": "gpt-4o-mini",
            "api": "openai",
            "key": openai_key
        }
    elif openrouter_key:
        # Try OpenRouter for GPT-4o-mini as fallback
        # Model ID from https://openrouter.ai/models/openai/gpt-4o-mini
        models["gpt4o-mini"] = {
            "id": "openai/gpt-4o-mini-2024-07-18",
            "api": "openrouter",
            "key": openrouter_key
        }

    if not models:
        print("No API keys configured!")
        return []

    test_cases = test_grader()
    results = []

    for case in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: {case['name']}")
        print(f"{'='*60}")

        messages = create_grading_prompt(case['title'], case['abstract'])

        case_results = {"name": case['name'], "expected": case['expected']}

        for model_name, config in models.items():
            print(f"\n{model_name}:")
            try:
                if config["api"] == "openrouter":
                    response = call_openrouter(messages, config["id"], config["key"])
                else:
                    response = call_openai(messages, config["id"], config["key"])

                content = response['choices'][0]['message']['content']

                # Parse JSON from response
                # Handle potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                parsed = json.loads(content.strip())
                case_results[model_name] = parsed

                print(f"  biomarker_use: {parsed.get('biomarker_use')}")
                print(f"  research_design: {parsed.get('research_design')}")
                print(f"  evidence_strength: {parsed.get('evidence_strength')}")
                print(f"  reasoning: {parsed.get('reasoning', '')[:100]}...")

            except Exception as e:
                print(f"  ERROR: {e}")
                case_results[model_name] = {"error": str(e)}

        results.append(case_results)

    return results


if __name__ == "__main__":
    import os
    from pathlib import Path

    # Try to load from .env file
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        print(f"Loading API keys from {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"\'')

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openrouter_key:
        print(f"OpenRouter API key loaded ({len(openrouter_key)} chars)")
    if openai_key:
        print(f"OpenAI API key loaded ({len(openai_key)} chars)")

    if not openrouter_key and not openai_key:
        print("Set OPENROUTER_API_KEY and/or OPENAI_API_KEY in .env file")
        print("  OpenRouter: https://openrouter.ai/keys")
        print("  OpenAI: https://platform.openai.com/api-keys")
        exit(1)

    results = run_comparison(openrouter_key=openrouter_key, openai_key=openai_key)

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "grader_comparison_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")
