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
    primary_term,
)

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

    # Ensure PRIMARY_TERM column exists
    if "PRIMARY_TERM" not in df.columns:
        df["PRIMARY_TERM"] = ""

    # Fill missing PRIMARY_TERM from MATCHED_TERMS (abstract-only grants have
    # MATCHED_TERMS but not PRIMARY_TERM from the filter script)
    mask = df["PRIMARY_TERM"].isna() | (df["PRIMARY_TERM"] == "")
    has_matched = mask & df["MATCHED_TERMS"].notna() & (df["MATCHED_TERMS"] != "")
    if has_matched.any():
        df.loc[has_matched, "PRIMARY_TERM"] = df.loc[has_matched, "MATCHED_TERMS"].apply(
            lambda mt: primary_term(mt.split(";"))
        )

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
