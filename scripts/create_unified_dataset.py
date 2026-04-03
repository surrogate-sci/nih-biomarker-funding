#!/usr/bin/env python3
"""
Create unified biomarker dataset by combining all filtered years and removing extraneous columns.

This script:
1. Reads keyword-match CSV files (biomarker_FY*.csv) and abstract-match CSV files
   (biomarker_abstract_FY*.csv)
2. Tags each grant with MATCH_SOURCE (keywords_only or abstract_only)
3. Deduplicates by (APPLICATION_ID, FY) — keyword rows take precedence
4. Keeps only analytically useful columns
5. Combines into a single unified CSV

Usage:
    python3 scripts/create_unified_dataset.py
"""

import argparse
import logging
import pandas as pd
from pathlib import Path
import sys


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging with appropriate level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


# Columns to keep in unified dataset
COLUMNS_TO_KEEP = [
    # Identifiers
    "APPLICATION_ID",
    "FY",
    "CORE_PROJECT_NUM",
    # Text content for analysis
    "PROJECT_TITLE",
    # PROJECT_TERMS - removed (too large, avg 1346 chars)
    # PHR - removed (29.7% empty, verbose)
    # Funding amounts
    "TOTAL_COST",
    "DIRECT_COST_AMT",
    "INDIRECT_COST_AMT",
    "TOTAL_COST_SUB_PROJECT",
    # Institute information
    "ADMINISTERING_IC",
    "IC_NAME",
    "FUNDING_ICs",
    # Timeline
    "PROJECT_START",
    "PROJECT_END",
    # People
    "PI_NAMEs",
    # Organization/Location
    "ORG_NAME",
    "ORG_STATE",
    "ORG_CITY",
    "ORG_COUNTRY",
    # Grant type
    "ACTIVITY",
    "APPLICATION_TYPE",
    "FUNDING_MECHANISM",
    # Categorization
    "NIH_SPENDING_CATS",
    "STUDY_SECTION",
    "STUDY_SECTION_NAME",
    # Our classification
    "EXPLICIT_BIOMARKER",
    "MATCHED_TERMS",
    "PRIMARY_TERM",
    "MATCH_SOURCE",
]


def _read_and_tag(
    file_path: Path,
    match_source: str,
    logger: logging.Logger,
) -> pd.DataFrame | None:
    """Read a filtered CSV, tag with MATCH_SOURCE, and keep only COLUMNS_TO_KEEP."""
    year_str = file_path.stem.replace("biomarker_abstract_FY", "").replace(
        "biomarker_FY", ""
    )
    label = f"FY{year_str} ({match_source})"
    logger.info(f"  Reading {label}...")

    try:
        df = pd.read_csv(file_path)
        df["MATCH_SOURCE"] = match_source

        existing_cols = [col for col in COLUMNS_TO_KEEP if col in df.columns]
        missing_cols = [
            col
            for col in COLUMNS_TO_KEEP
            if col not in df.columns and col != "MATCH_SOURCE"
        ]

        if missing_cols:
            logger.warning(f"    {label}: Missing columns: {missing_cols}")

        df_filtered = df[existing_cols].copy()
        logger.info(f"    {label}: {len(df_filtered):,} rows")
        return df_filtered

    except Exception as e:
        logger.error(f"    {label}: Error reading file: {e}")
        return None


def combine_filtered_years(
    filtered_dir: Path,
    output_path: Path,
    logger: logging.Logger,
) -> None:
    """Combine keyword-match and abstract-match files into unified dataset.

    Keyword files (biomarker_FY*.csv) are tagged MATCH_SOURCE='keywords_only'.
    Abstract files (biomarker_abstract_FY*.csv) are tagged MATCH_SOURCE='abstract_only'.
    Deduplication by (APPLICATION_ID, FY) keeps keyword rows over abstract rows.
    """

    # Find keyword-match files in keywords/ subdir (required)
    kw_dir = filtered_dir / "keywords"
    kw_pattern = "biomarker_FY*.csv"
    if kw_dir.exists():
        kw_files = sorted(kw_dir.glob(kw_pattern))
    else:
        # Fallback: flat layout (exclude abstract files)
        kw_files = sorted(
            f for f in filtered_dir.glob(kw_pattern) if "abstract" not in f.name
        )

    if not kw_files:
        logger.error(
            f"No keyword files found matching {kw_pattern} in {kw_dir if kw_dir.exists() else filtered_dir}"
        )
        sys.exit(1)

    # Find abstract-match files in abstracts/ subdir (optional)
    abs_dir = filtered_dir / "abstracts"
    abs_pattern = "biomarker_abstract_FY*.csv"
    if abs_dir.exists():
        abs_files = sorted(abs_dir.glob(abs_pattern))
    else:
        # Fallback: flat layout
        abs_files = sorted(filtered_dir.glob(abs_pattern))

    logger.info(f"Found {len(kw_files)} keyword files, {len(abs_files)} abstract files")

    all_data: list[pd.DataFrame] = []

    # Read keyword files
    for file_path in kw_files:
        df = _read_and_tag(file_path, "keywords_only", logger)
        if df is not None:
            all_data.append(df)

    # Read abstract files
    for file_path in abs_files:
        df = _read_and_tag(file_path, "abstract_only", logger)
        if df is not None:
            all_data.append(df)

    if not all_data:
        logger.error("No data was successfully loaded!")
        sys.exit(1)

    # Combine all files
    logger.info(f"\nCombining {len(all_data)} files...")
    combined_df = pd.concat(all_data, ignore_index=True)
    pre_dedup = len(combined_df)

    # Deduplicate by (APPLICATION_ID, FY) — keyword rows take precedence.
    # Sort so keywords_only comes before abstract_only, then drop duplicates
    # keeping first occurrence.
    source_order = {"keywords_only": 0, "abstract_only": 1}
    combined_df["_sort_key"] = combined_df["MATCH_SOURCE"].map(source_order)
    combined_df.sort_values("_sort_key", inplace=True)
    combined_df.drop_duplicates(
        subset=["APPLICATION_ID", "FY"], keep="first", inplace=True
    )
    combined_df.drop(columns=["_sort_key"], inplace=True)
    combined_df.sort_values(["FY", "APPLICATION_ID"], inplace=True)
    combined_df.reset_index(drop=True, inplace=True)

    dupes_removed = pre_dedup - len(combined_df)
    if dupes_removed > 0:
        logger.info(
            f"Removed {dupes_removed:,} duplicate (APPLICATION_ID, FY) rows "
            f"(keyword rows kept over abstract rows)"
        )

    # Report MATCH_SOURCE breakdown
    source_counts = combined_df["MATCH_SOURCE"].value_counts()
    logger.info("\nMATCH_SOURCE breakdown:")
    for source, count in source_counts.items():
        logger.info(f"  {source}: {count:,}")

    logger.info(
        f"\nCombined dataset: {len(combined_df):,} rows, "
        f"{len(combined_df.columns)} columns"
    )

    # Save unified dataset
    logger.info(f"Saving unified dataset to: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(output_path, index=False)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Unified dataset saved: {file_size_mb:.1f} MB")

    # Print column list
    logger.info(f"\nColumns in unified dataset ({len(combined_df.columns)}):")
    for i, col in enumerate(combined_df.columns, 1):
        logger.info(f"  {i:2d}. {col}")


def main():
    parser = argparse.ArgumentParser(
        description="Create unified biomarker dataset from filtered year files"
    )
    parser.add_argument(
        "--filtered-dir",
        type=Path,
        default=Path("data/filtered"),
        help="Directory containing filtered biomarker CSV files (default: data/filtered)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/nih_biomarker_unified_2004-2024.csv"),
        help="Output path for unified dataset (default: data/nih_biomarker_unified_2004-2024.csv)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup
    logger = setup_logging(args.verbose)

    # Check filtered directory exists
    if not args.filtered_dir.exists():
        logger.error(f"Filtered directory not found: {args.filtered_dir}")
        sys.exit(1)

    logger.info(f"Reading filtered data from: {args.filtered_dir}")
    logger.info(f"Output will be saved to: {args.output}")
    logger.info(f"Keeping {len(COLUMNS_TO_KEEP)} columns (removing extraneous columns)")

    # Combine years
    combine_filtered_years(args.filtered_dir, args.output, logger)

    logger.info("\nUnified dataset creation complete!")


if __name__ == "__main__":
    main()
