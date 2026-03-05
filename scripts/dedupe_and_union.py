#!/usr/bin/env python3
"""Deduplicate and union NIH Reporter CSV exports.

Reads NIH Reporter CSV files from an input directory, deduplicates by
Application ID + Fiscal Year, and writes a unified dataset.

Usage:
    python3 scripts/dedupe_and_union.py
    python3 scripts/dedupe_and_union.py --input-dir ~/Downloads/my-exports/data
    python3 scripts/dedupe_and_union.py --output data/oct-2024/nih_biomarker_unified.csv
"""

import argparse
import sys

import pandas as pd
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_INPUT_DIR = (
    Path.home()
    / "Downloads"
    / "NIH Reporter biomarker and surrogate endpoint spending"
    / "data"
)
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "oct-2024"


def load_nih_reporter_csv(filepath):
    """Load NIH Reporter CSV, skipping the header rows with search criteria.

    Args:
        filepath: Path to CSV file

    Returns:
        DataFrame
    """
    print(f"Loading {Path(filepath).name}...")

    # NIH Reporter CSVs have a header section with search criteria
    # We need to find where the actual data starts
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if line.startswith('"NIH Spending Categorization"'):
                skiprows = i
                break

    # Load the CSV starting from the actual data header
    df = pd.read_csv(filepath, skiprows=skiprows, low_memory=False)
    print(f"  Loaded {len(df):,} rows")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate and union NIH Reporter CSV exports"
    )
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help=f"Directory containing NIH Reporter CSV files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for unified dataset (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Full output file path (overrides --output-dir)",
    )
    args = parser.parse_args()

    data_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not data_dir.exists():
        print(f"ERROR: Input directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all CSV files
    csv_files = sorted(data_dir.glob("*.csv"))

    print("=" * 80)
    print(f"Found {len(csv_files)} CSV files to process")
    print("=" * 80)
    print()

    if not csv_files:
        print(f"ERROR: No CSV files found in {data_dir}", file=sys.stderr)
        sys.exit(1)

    # Load all CSVs
    dfs = []
    for csv_file in csv_files:
        df = load_nih_reporter_csv(csv_file)
        dfs.append(df)

    print()
    print("=" * 80)
    print("COMBINING AND DEDUPLICATING")
    print("=" * 80)

    # Concatenate all dataframes
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total rows before deduplication: {len(combined):,}")

    # Deduplicate based on Application ID AND Fiscal Year
    # Same grant in different fiscal years = different funding amounts, so keep both
    # This prevents eliminating legitimate year-over-year funding entries
    deduplicated = combined.drop_duplicates(
        subset=["Application ID", "Fiscal Year"], keep="first"
    )

    print(f"Total rows after deduplication: {len(deduplicated):,}")
    print(f"Removed {len(combined) - len(deduplicated):,} duplicate rows")

    # Sort by Fiscal Year and Application ID for easier browsing
    deduplicated = deduplicated.sort_values(
        ["Fiscal Year", "Application ID"], ascending=[False, True]
    )

    print()
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    # Show fiscal year distribution
    print("\nProjects by Fiscal Year:")
    fy_counts = deduplicated["Fiscal Year"].value_counts().sort_index()
    for year, count in fy_counts.items():
        print(f"  FY{year}: {count:,} projects")

    # Show top institutes
    print("\nTop 10 Institutes by Number of Projects:")
    institute_counts = deduplicated["Administering IC"].value_counts().head(10)
    for institute, count in institute_counts.items():
        print(f"  {institute}: {count:,} projects")

    print()
    print("=" * 80)
    print("SAVING UNIFIED DATASET")
    print("=" * 80)

    # Save the deduplicated dataset
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_file = output_dir / "nih_biomarker_unified.csv"

    deduplicated.to_csv(output_file, index=False)

    print(f"\nSaved unified dataset to: {output_file}")
    print(f"  Total projects: {len(deduplicated):,}")
    print(f"  File size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
