#!/usr/bin/env python3
"""
Filter for 'intermediate outcomes', 'intermediate endpoints', or 'surrogate endpoints'
and analyze funding by year
"""

import pandas as pd
from pathlib import Path

def main():
    # Load unified dataset (relative to project root)
    script_dir = Path(__file__).parent.parent
    data_file = script_dir / "data" / "oct-2024" / "nih_biomarker_unified.csv"
    print(f"Loading {data_file.name}...")
    df = pd.read_csv(data_file, low_memory=False)
    print(f"Total projects: {len(df):,}\n")

    # Filter for surrogate/intermediate endpoint keywords
    print("=" * 80)
    print("FILTERING FOR SURROGATE/INTERMEDIATE ENDPOINTS")
    print("=" * 80)

    keywords = [
        'intermediate outcomes',
        'intermediate endpoint',
        'surrogate endpoint'
    ]

    print(f"Searching for: {', '.join(keywords)}\n")

    # Search in Project Title, Project Terms, and Public Health Relevance
    text_fields = ['Project Title', 'Project Terms', 'Public Health Relevance']

    # Track matches per keyword
    for keyword in keywords:
        keyword_mask = pd.Series([False] * len(df), index=df.index)
        for field in text_fields:
            if field in df.columns:
                field_mask = df[field].astype(str).str.lower().str.contains(keyword, na=False)
                keyword_mask = keyword_mask | field_mask
        print(f"  '{keyword}': {keyword_mask.sum():,} projects")

    # Combined mask (any keyword in any field)
    mask = pd.Series([False] * len(df), index=df.index)
    for field in text_fields:
        if field in df.columns:
            for keyword in keywords:
                field_mask = df[field].astype(str).str.lower().str.contains(keyword, na=False)
                mask = mask | field_mask

    filtered_df = df[mask].copy()
    print(f"\nTotal projects with any surrogate/intermediate endpoint term: {len(filtered_df):,}")
    print(f"Percentage of dataset: {len(filtered_df)/len(df)*100:.1f}%\n")

    # Summarize funding by year
    print("=" * 80)
    print("FUNDING BY FISCAL YEAR")
    print("=" * 80)

    # Convert Total Cost to numeric, handling any non-numeric values
    filtered_df['Total Cost Numeric'] = pd.to_numeric(filtered_df['Total Cost'], errors='coerce')

    # Group by fiscal year
    yearly_summary = filtered_df.groupby('Fiscal Year').agg({
        'Application ID': 'count',
        'Total Cost Numeric': 'sum'
    }).reset_index()

    yearly_summary.columns = ['Fiscal Year', 'Number of Projects', 'Total Funding ($)']

    # Format funding in millions
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
    print("TOP 10 INSTITUTES FOR SURROGATE/INTERMEDIATE ENDPOINTS")
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
    output_file = script_dir / "data" / "oct-2024" / "surrogate_endpoints_filtered.csv"
    filtered_df.to_csv(output_file, index=False)
    print(f"\n✓ Filtered dataset saved to: data/oct-2024/{output_file.name}")
    print(f"  Size: {output_file.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()
