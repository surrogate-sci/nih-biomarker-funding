#!/usr/bin/env python3
"""
Unified keyword analysis script for NIH biomarker funding data
Usage:
    python3 analyze_keywords.py "biomarker discovery"
    python3 analyze_keywords.py "surrogate endpoint" "intermediate endpoint"
    python3 analyze_keywords.py --all-biomarkers
"""

import pandas as pd
import sys
from pathlib import Path

def analyze_keywords(keywords, output_name=None):
    """
    Analyze NIH projects containing specified keywords

    Args:
        keywords: List of keywords to search for
        output_name: Optional custom name for output files
    """
    # Load unified dataset (relative to project root)
    script_dir = Path(__file__).parent.parent
    data_file = script_dir / "data" / "oct-2024" / "nih_biomarker_unified.csv"
    print(f"Loading {data_file.name}...")
    df = pd.read_csv(data_file, low_memory=False)
    print(f"Total projects: {len(df):,}\n")

    # Filter for keywords
    print("=" * 80)
    print(f"FILTERING FOR KEYWORDS: {', '.join(keywords)}")
    print("=" * 80)

    # Search in Project Title, Project Terms, and Public Health Relevance
    text_fields = ['Project Title', 'Project Terms', 'Public Health Relevance']

    # Track matches per keyword
    for keyword in keywords:
        keyword_mask = pd.Series([False] * len(df), index=df.index)
        for field in text_fields:
            if field in df.columns:
                field_mask = df[field].astype(str).str.lower().str.contains(keyword.lower(), na=False)
                keyword_mask = keyword_mask | field_mask
        print(f"  '{keyword}': {keyword_mask.sum():,} projects")

    # Combined mask (any keyword in any field)
    mask = pd.Series([False] * len(df), index=df.index)
    for field in text_fields:
        if field in df.columns:
            for keyword in keywords:
                field_mask = df[field].astype(str).str.lower().str.contains(keyword.lower(), na=False)
                mask = mask | field_mask

    filtered_df = df[mask].copy()
    print(f"\nTotal projects matching any keyword: {len(filtered_df):,}")
    print(f"Percentage of dataset: {len(filtered_df)/len(df)*100:.1f}%\n")

    # Summarize funding by year
    print("=" * 80)
    print("FUNDING BY FISCAL YEAR")
    print("=" * 80)

    # Convert Total Cost to numeric
    filtered_df['Total Cost Numeric'] = pd.to_numeric(filtered_df['Total Cost'], errors='coerce')

    # Group by fiscal year
    yearly_summary = filtered_df.groupby('Fiscal Year').agg({
        'Application ID': 'count',
        'Total Cost Numeric': 'sum'
    }).reset_index()

    yearly_summary.columns = ['Fiscal Year', 'Number of Projects', 'Total Funding ($)']
    yearly_summary['Total Funding (Millions)'] = yearly_summary['Total Funding ($)'] / 1_000_000

    # Print summary
    print("\nYear | Projects | Total Funding")
    print("-" * 50)
    for _, row in yearly_summary.iterrows():
        year = int(row['Fiscal Year'])
        projects = int(row['Number of Projects'])
        funding_m = row['Total Funding (Millions)']
        print(f"{year} | {projects:>8} | ${funding_m:>10,.2f}M")

    # Overall statistics
    print("\n" + "=" * 80)
    print("OVERALL STATISTICS")
    print("=" * 80)
    total_projects = yearly_summary['Number of Projects'].sum()
    total_funding = yearly_summary['Total Funding ($)'].sum()
    avg_per_project = total_funding / total_projects if total_projects > 0 else 0

    print(f"Total Projects: {total_projects:,}")
    print(f"Total Funding: ${total_funding/1_000_000:,.2f}M")
    print(f"Average per Project: ${avg_per_project:,.0f}")
    print(f"Years Covered: {int(yearly_summary['Fiscal Year'].min())} - {int(yearly_summary['Fiscal Year'].max())}")

    # Top institutes
    print("\n" + "=" * 80)
    print("TOP 10 INSTITUTES")
    print("=" * 80)

    institute_summary = filtered_df.groupby('Administering IC').agg({
        'Application ID': 'count',
        'Total Cost Numeric': 'sum'
    }).reset_index()

    institute_summary.columns = ['Institute', 'Number of Projects', 'Total Funding ($)']
    institute_summary = institute_summary.sort_values('Total Funding ($)', ascending=False).head(10)

    print("\nInstitute | Projects | Total Funding")
    print("-" * 60)
    for _, row in institute_summary.iterrows():
        institute = row['Institute']
        projects = int(row['Number of Projects'])
        funding_m = row['Total Funding ($)'] / 1_000_000
        print(f"{institute:<10} | {projects:>8} | ${funding_m:>10,.2f}M")

    # Save filtered dataset
    if output_name is None:
        # Generate filename from keywords
        output_name = "_".join(keywords).replace(" ", "_")[:50]  # Limit length

    output_file = script_dir / "data" / "oct-2024" / f"{output_name}_filtered.csv"
    filtered_df.to_csv(output_file, index=False)
    print(f"\n✓ Filtered dataset saved to: data/oct-2024/{output_file.name}")
    print(f"  Size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

def print_usage():
    """Print usage information"""
    print("""
Usage: python3 analyze_keywords.py [OPTIONS] KEYWORD [KEYWORD ...]

Analyze NIH biomarker funding data by searching for specific keywords.

Examples:
    # Single keyword
    python3 analyze_keywords.py "biomarker discovery"

    # Multiple keywords (OR search)
    python3 analyze_keywords.py "surrogate endpoint" "intermediate endpoint"

    # All biomarker projects
    python3 analyze_keywords.py "biomarker"

    # With custom output name
    python3 analyze_keywords.py "surrogate" -o surrogate_analysis

Options:
    -o, --output NAME    Custom name for output files (default: auto-generated from keywords)
    -h, --help          Show this help message

The script searches for keywords in:
    - Project Title
    - Project Terms
    - Public Health Relevance
""")

def main():
    """Main entry point"""
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print_usage()
        sys.exit(0 if '--help' in sys.argv or '-h' in sys.argv else 1)

    # Parse arguments
    args = sys.argv[1:]
    output_name = None
    keywords = []

    i = 0
    while i < len(args):
        if args[i] in ['-o', '--output']:
            if i + 1 < len(args):
                output_name = args[i + 1]
                i += 2
            else:
                print("Error: -o/--output requires a value")
                sys.exit(1)
        else:
            keywords.append(args[i])
            i += 1

    if not keywords:
        print("Error: At least one keyword is required")
        print_usage()
        sys.exit(1)

    # Run analysis
    analyze_keywords(keywords, output_name)

if __name__ == "__main__":
    main()
