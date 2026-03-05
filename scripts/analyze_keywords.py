#!/usr/bin/env python3
"""Unified keyword analysis script for NIH biomarker funding data.

Searches the unified dataset for projects matching specified keywords and
produces funding summaries by fiscal year and institute.

Usage:
    python3 scripts/analyze_keywords.py "biomarker discovery"
    python3 scripts/analyze_keywords.py "surrogate endpoint" "intermediate endpoint"
    python3 scripts/analyze_keywords.py --input data/nih_biomarker_unified_2004-2024.csv "biomarker"
    python3 scripts/analyze_keywords.py --output-dir data/oct-2024 -o surrogate_analysis "surrogate"
"""

import argparse
import sys

import pandas as pd
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_INPUT = DEFAULT_DATA_DIR / "oct-2024" / "nih_biomarker_unified.csv"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "oct-2024"


def analyze_keywords(keywords, input_file, output_dir, output_name=None):
    """Analyze NIH projects containing specified keywords.

    Args:
        keywords: List of keywords to search for
        input_file: Path to unified dataset CSV
        output_dir: Directory for output files
        output_name: Optional custom name for output files
    """
    # Load unified dataset
    print(f"Loading {input_file.name}...")
    df = pd.read_csv(input_file, low_memory=False)
    print(f"Total projects: {len(df):,}\n")

    # Filter for keywords
    print("=" * 80)
    print(f"FILTERING FOR KEYWORDS: {', '.join(keywords)}")
    print("=" * 80)

    # Search in Project Title, Project Terms, and Public Health Relevance
    text_fields = ["Project Title", "Project Terms", "Public Health Relevance"]

    # Track matches per keyword
    for keyword in keywords:
        keyword_mask = pd.Series([False] * len(df), index=df.index)
        for field in text_fields:
            if field in df.columns:
                field_mask = (
                    df[field]
                    .astype(str)
                    .str.lower()
                    .str.contains(keyword.lower(), na=False)
                )
                keyword_mask = keyword_mask | field_mask
        print(f"  '{keyword}': {keyword_mask.sum():,} projects")

    # Combined mask (any keyword in any field)
    mask = pd.Series([False] * len(df), index=df.index)
    for field in text_fields:
        if field in df.columns:
            for keyword in keywords:
                field_mask = (
                    df[field]
                    .astype(str)
                    .str.lower()
                    .str.contains(keyword.lower(), na=False)
                )
                mask = mask | field_mask

    filtered_df = df[mask].copy()
    print(f"\nTotal projects matching any keyword: {len(filtered_df):,}")
    print(f"Percentage of dataset: {len(filtered_df)/len(df)*100:.1f}%\n")

    # Summarize funding by year
    print("=" * 80)
    print("FUNDING BY FISCAL YEAR")
    print("=" * 80)

    # Convert Total Cost to numeric
    filtered_df["Total Cost Numeric"] = pd.to_numeric(
        filtered_df["Total Cost"], errors="coerce"
    )

    # Group by fiscal year
    yearly_summary = (
        filtered_df.groupby("Fiscal Year")
        .agg({"Application ID": "count", "Total Cost Numeric": "sum"})
        .reset_index()
    )

    yearly_summary.columns = ["Fiscal Year", "Number of Projects", "Total Funding ($)"]
    yearly_summary["Total Funding (Millions)"] = (
        yearly_summary["Total Funding ($)"] / 1_000_000
    )

    # Print summary
    print("\nYear | Projects | Total Funding")
    print("-" * 50)
    for _, row in yearly_summary.iterrows():
        year = int(row["Fiscal Year"])
        projects = int(row["Number of Projects"])
        funding_m = row["Total Funding (Millions)"]
        print(f"{year} | {projects:>8} | ${funding_m:>10,.2f}M")

    # Overall statistics
    print("\n" + "=" * 80)
    print("OVERALL STATISTICS")
    print("=" * 80)
    total_projects = yearly_summary["Number of Projects"].sum()
    total_funding = yearly_summary["Total Funding ($)"].sum()
    avg_per_project = total_funding / total_projects if total_projects > 0 else 0

    print(f"Total Projects: {total_projects:,}")
    print(f"Total Funding: ${total_funding/1_000_000:,.2f}M")
    print(f"Average per Project: ${avg_per_project:,.0f}")
    print(
        f"Years Covered: {int(yearly_summary['Fiscal Year'].min())} - {int(yearly_summary['Fiscal Year'].max())}"
    )

    # Top institutes
    print("\n" + "=" * 80)
    print("TOP 10 INSTITUTES")
    print("=" * 80)

    institute_summary = (
        filtered_df.groupby("Administering IC")
        .agg({"Application ID": "count", "Total Cost Numeric": "sum"})
        .reset_index()
    )

    institute_summary.columns = ["Institute", "Number of Projects", "Total Funding ($)"]
    institute_summary = institute_summary.sort_values(
        "Total Funding ($)", ascending=False
    ).head(10)

    print("\nInstitute | Projects | Total Funding")
    print("-" * 60)
    for _, row in institute_summary.iterrows():
        institute = row["Institute"]
        projects = int(row["Number of Projects"])
        funding_m = row["Total Funding ($)"] / 1_000_000
        print(f"{institute:<10} | {projects:>8} | ${funding_m:>10,.2f}M")

    # Save filtered dataset
    if output_name is None:
        # Generate filename from keywords
        output_name = "_".join(keywords).replace(" ", "_")[:50]  # Limit length

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{output_name}_filtered.csv"
    filtered_df.to_csv(output_file, index=False)
    print(f"\nFiltered dataset saved to: {output_file}")
    print(f"  Size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze NIH biomarker funding data by searching for specific keywords"
    )
    parser.add_argument(
        "keywords",
        nargs="*",
        help="Keywords to search for (OR search across Project Title, Project Terms, Public Health Relevance)",
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help=f"Path to unified dataset CSV (default: {DEFAULT_INPUT.relative_to(DEFAULT_DATA_DIR.parent)})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory for filtered CSVs (default: {DEFAULT_OUTPUT_DIR.relative_to(DEFAULT_DATA_DIR.parent)})",
    )
    parser.add_argument(
        "-o",
        "--output-name",
        default=None,
        help="Custom name for output files (default: auto-generated from keywords)",
    )
    args = parser.parse_args()

    if not args.keywords:
        parser.print_help()
        sys.exit(1)

    input_file = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    analyze_keywords(args.keywords, input_file, output_dir, args.output_name)


if __name__ == "__main__":
    main()
