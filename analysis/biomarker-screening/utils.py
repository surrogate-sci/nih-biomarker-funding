"""Utilities for biomarker screening analysis.

Loads and cleans the unified NIH biomarker dataset.
Computes per-grant PRIMARY_TERM from keyword_terms.py when not present.
"""

import sys
from pathlib import Path

import pandas as pd

# Project root: analysis/biomarker-screening/../../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "nih_biomarker_unified_2004-2024.csv"

# Make scripts/ importable so we can use keyword_terms
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from keyword_terms import (  # noqa: E402
    EXPANDED_BIOMARKER_TERMS,
    find_matching_terms,
    primary_term,
)

# Functional categories for biomarker terms — grouped by research PURPOSE.
# Maps each of the 36 expanded terms to one of 6 purpose categories.
# These categories address the core question: what kind of biomarker work
# does NIH fund, and how much is surrogacy/endpoint validation?
TERM_PURPOSE = {
    # Surrogacy & endpoint validation — the hypothesis target
    "surrogate endpoint": "Surrogacy & endpoint validation",
    "intermediate outcome": "Surrogacy & endpoint validation",
    "intermediate endpoint": "Surrogacy & endpoint validation",
    "digital endpoint": "Surrogacy & endpoint validation",
    # Clinical decision-making — specific use of biomarkers in patient care
    "companion diagnostic": "Clinical decision-making",
    "risk stratification": "Clinical decision-making",
    "patient selection": "Clinical decision-making",
    "predicting response": "Clinical decision-making",
    "response to therapy": "Clinical decision-making",
    # Discovery & identification — naming or finding biomarkers
    "biomarker": "Discovery & identification",
    "clinical marker": "Discovery & identification",
    "imaging marker": "Discovery & identification",
    "digital biomarker": "Discovery & identification",
    "genetic marker": "Discovery & identification",
    "endophenotype": "Discovery & identification",
    # Diagnostics & prognostics — test performance and prediction
    "diagnostic accuracy": "Diagnostics & prognostics",
    "diagnostic sensitivity": "Diagnostics & prognostics",
    "diagnostic specificity": "Diagnostics & prognostics",
    "clinical diagnostics": "Diagnostics & prognostics",
    "personalized diagnostics": "Diagnostics & prognostics",
    "clinical predictors": "Diagnostics & prognostics",
    "prognostic value": "Diagnostics & prognostics",
    "prognostic assays": "Diagnostics & prognostics",
    "clinically actionable": "Diagnostics & prognostics",
    # Stratification & precision medicine
    "patient stratification": "Stratification & precision medicine",
    "disease stratification": "Stratification & precision medicine",
    "disease heterogeneity": "Stratification & precision medicine",
    "clinical subtypes": "Stratification & precision medicine",
    "theranostics": "Stratification & precision medicine",
    "precision oncology": "Stratification & precision medicine",
    "predictive signature": "Stratification & precision medicine",
    "genomic signature": "Stratification & precision medicine",
    "proteomic signature": "Stratification & precision medicine",
    "biosignature": "Stratification & precision medicine",
    # Broad biomarker-adjacent — AND-condition keyword catches
    "clinical+omics": "Broad biomarker-adjacent",
    "clinical+imaging": "Broad biomarker-adjacent",
}

# Verify all expanded terms are mapped
_unmapped = set(EXPANDED_BIOMARKER_TERMS) - set(TERM_PURPOSE.keys())
assert not _unmapped, f"Unmapped terms: {_unmapped}"

# Display order: hypothesis-relevant first, broadest last
PURPOSE_ORDER = [
    "Surrogacy & endpoint validation",
    "Clinical decision-making",
    "Discovery & identification",
    "Diagnostics & prognostics",
    "Stratification & precision medicine",
    "Broad biomarker-adjacent",
]

# Colors for purpose categories (Paul Tol qualitative)
PURPOSE_COLORS = {
    "Surrogacy & endpoint validation": "#CC6677",   # rose — highlight
    "Clinical decision-making": "#332288",           # indigo
    "Discovery & identification": "#88CCEE",         # cyan
    "Diagnostics & prognostics": "#44AA99",          # teal
    "Stratification & precision medicine": "#999933", # olive
    "Broad biomarker-adjacent": "#BBBBBB",           # grey
}

# Years with known PROJECT_TERMS data quality issues
# FY2005: PROJECT_TERMS 68% populated; FY2006: empty
# FY2013, FY2018: anomalous keyword counts (partially compensated by abstract search)
DATA_QUALITY_YEARS = {2005, 2006, 2013, 2018}


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Load the unified biomarker dataset with type cleaning.

    Returns DataFrame with:
    - EXPLICIT_BIOMARKER as bool
    - TOTAL_COST as float (NaN for missing)
    - FY as int
    - PRIMARY_TERM from filter script (keyword-matched grants) or title fallback
      (abstract-only grants). 100% coverage for keyword-matched, partial for abstract-only.
    """
    df = pd.read_csv(
        path,
        dtype={"APPLICATION_ID": str, "ADMINISTERING_IC": str, "ACTIVITY": str},
        low_memory=False,
    )
    df["EXPLICIT_BIOMARKER"] = df["EXPLICIT_BIOMARKER"].fillna(False).astype(bool)
    df["TOTAL_COST"] = pd.to_numeric(df["TOTAL_COST"], errors="coerce")
    df["FY"] = df["FY"].astype(int)

    # Ensure PRIMARY_TERM column exists — compute from available data
    if "PRIMARY_TERM" not in df.columns:
        if "MATCHED_TERMS" in df.columns:
            # Dataset has MATCHED_TERMS from enriched filter pipeline
            df["PRIMARY_TERM"] = ""
            mask = df["PRIMARY_TERM"].isna() | (df["PRIMARY_TERM"] == "")
            has_matched = (
                mask & df["MATCHED_TERMS"].notna() & (df["MATCHED_TERMS"] != "")
            )
            if has_matched.any():
                df.loc[has_matched, "PRIMARY_TERM"] = df.loc[
                    has_matched, "MATCHED_TERMS"
                ].apply(lambda mt: primary_term(mt.split(";")))
        else:
            # Older dataset without MATCHED_TERMS — derive from PROJECT_TITLE
            print("  Computing PRIMARY_TERM from PROJECT_TITLE (no MATCHED_TERMS column)...")
            df["PRIMARY_TERM"] = df["PROJECT_TITLE"].fillna("").apply(
                lambda t: primary_term(find_matching_terms(t, EXPANDED_BIOMARKER_TERMS))
            )
    else:
        # Fill blanks from MATCHED_TERMS if available
        mask = df["PRIMARY_TERM"].isna() | (df["PRIMARY_TERM"] == "")
        if "MATCHED_TERMS" in df.columns:
            has_matched = (
                mask & df["MATCHED_TERMS"].notna() & (df["MATCHED_TERMS"] != "")
            )
            if has_matched.any():
                df.loc[has_matched, "PRIMARY_TERM"] = df.loc[
                    has_matched, "MATCHED_TERMS"
                ].apply(lambda mt: primary_term(mt.split(";")))

    return df


def activity_category(activity: str) -> str:
    """Map NIH activity codes to broad categories."""
    if not isinstance(activity, str) or len(activity) < 1:
        return "Other"
    prefix = activity[0].upper()
    category_map = {
        "R": "Research (R)",
        "P": "Program/Center (P)",
        "U": "Cooperative (U)",
        "K": "Career Dev (K)",
        "T": "Training (T)",
        "F": "Fellowship (F)",
    }
    return category_map.get(prefix, "Other")
