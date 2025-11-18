#!/usr/bin/env python3
"""
Create unified biomarker dataset by combining all filtered years and removing extraneous columns.

This script:
1. Reads all filtered biomarker CSV files (FY2004-2024)
2. Keeps only analytically useful columns
3. Combines into a single unified CSV

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
]


def combine_filtered_years(
    filtered_dir: Path,
    output_path: Path,
    logger: logging.Logger,
) -> None:
    """Combine all filtered year files into unified dataset with selected columns."""

    # Find all filtered files
    pattern = "biomarker_FY*.csv"
    files = sorted(filtered_dir.glob(pattern))

    if not files:
        logger.error(f"No filtered files found matching {pattern} in {filtered_dir}")
        sys.exit(1)

    logger.info(f"Found {len(files)} filtered year files")

    all_data = []
    total_rows = 0

    for file_path in files:
        year_str = file_path.stem.replace("biomarker_FY", "")
        logger.info(f"  Reading FY{year_str}...")

        try:
            df = pd.read_csv(file_path)

            # Check which columns exist and keep only those
            existing_cols = [col for col in COLUMNS_TO_KEEP if col in df.columns]
            missing_cols = [col for col in COLUMNS_TO_KEEP if col not in df.columns]

            if missing_cols:
                logger.warning(f"    FY{year_str}: Missing columns: {missing_cols}")

            # Keep only the columns we want
            df_filtered = df[existing_cols].copy()

            all_data.append(df_filtered)
            total_rows += len(df_filtered)
            logger.info(f"    FY{year_str}: {len(df_filtered):,} rows, {len(existing_cols)} columns")

        except Exception as e:
            logger.error(f"    FY{year_str}: Error reading file: {e}")
            continue

    if not all_data:
        logger.error("No data was successfully loaded!")
        sys.exit(1)

    # Combine all years
    logger.info(f"\nCombining {len(all_data)} fiscal years...")
    combined_df = pd.concat(all_data, ignore_index=True)

    logger.info(f"Combined dataset: {len(combined_df):,} rows, {len(combined_df.columns)} columns")

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
