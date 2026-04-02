"""Utilities for biomarker screening analysis.

Loads and cleans the unified NIH biomarker dataset.
"""

from pathlib import Path

import pandas as pd

# Project root: analysis/biomarker-screening/../../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "nih_biomarker_unified_2004-2024.csv"

# Years with known PROJECT_TERMS data quality issues
DATA_QUALITY_YEARS = {2005, 2006}


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Load the unified biomarker dataset with type cleaning.

    Returns DataFrame with:
    - EXPLICIT_BIOMARKER as bool
    - TOTAL_COST as float (NaN for missing)
    - FY as int
    """
    df = pd.read_csv(
        path,
        dtype={"APPLICATION_ID": str, "ADMINISTERING_IC": str, "ACTIVITY": str},
        low_memory=False,
    )
    df["EXPLICIT_BIOMARKER"] = df["EXPLICIT_BIOMARKER"].fillna(False).astype(bool)
    df["TOTAL_COST"] = pd.to_numeric(df["TOTAL_COST"], errors="coerce")
    df["FY"] = df["FY"].astype(int)
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
