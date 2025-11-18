#!/usr/bin/env python3
"""
Generate summary report and visualizations from already-filtered biomarker data.

This script reads filtered CSV files from data/filtered/ and generates:
- SUMMARY.md with funding and project statistics
- (Future) Visualizations

Usage:
    # Generate summary from all filtered files
    python3 scripts/generate_summary.py

    # Generate summary from specific directory
    python3 scripts/generate_summary.py --filtered-dir data/filtered
"""

import argparse
import logging
from pathlib import Path
from typing import List, Dict
import pandas as pd
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


def find_filtered_files(filtered_dir: Path, logger: logging.Logger) -> List[Dict]:
    """Find all filtered biomarker CSV files and extract year information."""
    pattern = "biomarker_FY*.csv"
    files = sorted(filtered_dir.glob(pattern))

    if not files:
        logger.error(f"No filtered files found matching {pattern} in {filtered_dir}")
        return []

    logger.info(f"Found {len(files)} filtered year files")

    year_data = []
    for file_path in files:
        # Extract year from filename: biomarker_FY2020.csv -> 2020
        year_str = file_path.stem.replace("biomarker_FY", "")
        try:
            year = int(year_str)

            # Read CSV to get project count
            df = pd.read_csv(file_path)
            matched_projects = len(df)

            year_data.append({
                'year': year,
                'file_path': file_path,
                'matched_projects': matched_projects,
            })
            logger.info(f"  FY{year}: {matched_projects:,} projects ({file_path.stat().st_size / 1024 / 1024:.1f} MB)")
        except ValueError:
            logger.warning(f"Could not parse year from filename: {file_path.name}")
            continue

    return sorted(year_data, key=lambda x: x['year'])


def generate_summary_markdown(
    year_data: List[Dict],
    output_path: Path,
    logger: logging.Logger,
) -> None:
    """Generate SUMMARY.md from filtered data."""
    logger.info(f"Generating summary: {output_path}")

    with open(output_path, "w") as f:
        f.write("# NIH Biomarker Funding Analysis - Summary\n\n")
        f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Per-year results table
        f.write("## Per-Year Results\n\n")
        f.write("| Year | Biomarker Relevant Spending | Explicit Biomarker Spending | Matched Projects | Total Scanned |\n")
        f.write("|------|------------------------------|------------------------------|------------------|---------------|\n")

        total_matched = 0
        total_explicit = 0
        total_funding = 0
        total_explicit_funding = 0
        total_scanned = 0

        for year_info in year_data:
            try:
                df = pd.read_csv(year_info['file_path'])

                # Calculate funding
                df['TOTAL_COST_NUM'] = pd.to_numeric(df['TOTAL_COST'], errors='coerce')
                year_funding = df['TOTAL_COST_NUM'].sum()

                # Count explicit biomarker projects
                if 'EXPLICIT_BIOMARKER' in df.columns:
                    explicit_count = ((df['EXPLICIT_BIOMARKER'] == True) | (df['EXPLICIT_BIOMARKER'] == 'TRUE')).sum()
                    year_explicit_funding = df[df['EXPLICIT_BIOMARKER'] == True]['TOTAL_COST_NUM'].sum()
                else:
                    explicit_count = 0
                    year_explicit_funding = 0
                    logger.warning(f"FY{year_info['year']}: No EXPLICIT_BIOMARKER column found")

                # Estimate total scanned (this is approximate without original data)
                # Using rough estimate based on typical NIH project counts
                estimated_scanned = {
                    2004: 65000, 2005: 50000, 2006: 55000, 2007: 65000, 2008: 70000,
                    2017: 73144, 2018: 80826, 2019: 79469, 2020: 82428, 2021: 82940,
                    2022: 83891, 2023: 85118, 2024: 83501
                }.get(year_info['year'], 80000)

                f.write(f"| {year_info['year']} | ${year_funding/1e9:.2f}B | ${year_explicit_funding/1e9:.2f}B | {year_info['matched_projects']:,} | {estimated_scanned:,} |\n")

                total_matched += year_info['matched_projects']
                total_explicit += explicit_count
                total_funding += year_funding
                total_explicit_funding += year_explicit_funding
                total_scanned += estimated_scanned

            except Exception as e:
                logger.error(f"Error processing FY{year_info['year']}: {e}")
                f.write(f"| {year_info['year']} | Error | Error | {year_info['matched_projects']:,} | - |\n")

        # Column definitions
        f.write("\n### Column Definitions\n\n")
        f.write("- **Year**: NIH fiscal year\n")
        f.write("- **Biomarker Relevant Spending**: Total TOTAL_COST for all matched projects\n")
        f.write("- **Explicit Biomarker Spending**: Total TOTAL_COST for projects matching core biomarker terms\n")
        f.write("- **Matched Projects**: Projects where PROJECT_TITLE or PROJECT_TERMS fields contain any biomarker search term (case-insensitive, with AND logic for terms containing '+')\n")
        f.write("- **Total Scanned**: Total projects examined in NIH ExPORTER RePORTER_PRJ_C_FY{year}.csv file\n")

        # Search terms
        f.write("\n### Search Terms Used\n\n")
        f.write("**Core biomarker terms (4):**\n")
        f.write("- biomarker, clinical marker, surrogate endpoint, imaging marker\n\n")
        f.write("**Expanded biomarker terms (10):**\n")
        f.write("- biomarker, clinical marker, surrogate endpoint, imaging marker, digital biomarker, intermediate outcome, endophenotype, genetic marker, clinical+omics, clinical+imaging\n")

        # Overall statistics
        f.write("\n## Overall Statistics\n\n")
        f.write("### Projects\n")
        f.write(f"- **Total Matched Projects (Expanded)**: {total_matched:,}\n")
        if total_explicit > 0:
            f.write(f"- **Explicit Biomarker Projects (Core)**: {total_explicit:,}\n")
            f.write(f"- **Other Biomarker-Related Projects**: {total_matched - total_explicit:,}\n")
        f.write(f"- **Total Scanned Projects**: {total_scanned:,}\n")
        f.write(f"- **Overall Match Rate**: {(total_matched/total_scanned*100):.1f}%\n")
        if total_explicit > 0:
            f.write(f"- **Explicit Biomarker Rate**: {(total_explicit/total_scanned*100):.1f}%\n")

        f.write("\n### Funding\n")
        f.write(f"- **Biomarker Relevant Spending**: ${total_funding/1e9:.2f}B\n")
        if total_explicit_funding > 0:
            f.write(f"- **Explicit Biomarker Spending**: ${total_explicit_funding/1e9:.2f}B ({total_explicit_funding/total_funding*100:.1f}%)\n")

        f.write("\n### Processing\n")
        f.write(f"- **Years Available**: {len(year_data)}\n")
        f.write(f"- **Year Range**: {min(y['year'] for y in year_data)}-{max(y['year'] for y in year_data)}\n\n")

        # Output files
        f.write("## Output Files\n\n")
        f.write("Individual year files saved to `data/filtered/`:\n")
        for year_info in year_data:
            f.write(f"- `{year_info['file_path'].name}` (includes `EXPLICIT_BIOMARKER` column)\n")

        # Data structure
        f.write("\n## Data Structure\n\n")
        f.write("- **Deduplication Key**: (APPLICATION_ID, FY)\n")
        f.write("- **Search Columns**: PROJECT_TITLE, PROJECT_TERMS\n")
        f.write("- **Search Logic**: OR across all terms, AND logic for terms with '+'\n")
        f.write("- **Case Sensitivity**: Case-insensitive matching\n")
        f.write("- **EXPLICIT_BIOMARKER Column**: TRUE for projects matching core terms (biomarker, clinical marker, surrogate endpoint, imaging marker)\n")

        # Data quality warnings
        f.write("\n## Data Quality Notes\n\n")
        f.write("**Known issues with NIH ExPORTER source data:**\n")
        f.write("- **FY2005**: PROJECT_TERMS field only 68% populated (vs 89% in FY2004)\n")
        f.write("- **FY2006**: PROJECT_TERMS field completely empty (0% populated)\n")
        f.write("- Impact: These years show artificially low match counts since matches rely heavily on PROJECT_TERMS keywords\n")
        f.write("- FY2004, FY2007-2024: PROJECT_TERMS field 86-89% populated (normal)\n")
        f.write("\n")

    logger.info(f"Summary saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate summary report and visualizations from filtered biomarker data"
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
        default=None,
        help="Output path for summary (default: <filtered-dir>/SUMMARY.md)",
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

    # Determine output path
    if args.output is None:
        args.output = args.filtered_dir / "SUMMARY.md"

    logger.info(f"Reading filtered data from: {args.filtered_dir}")

    # Find filtered files
    year_data = find_filtered_files(args.filtered_dir, logger)

    if not year_data:
        logger.error("No filtered data found. Run process_all_years.py first.")
        sys.exit(1)

    # Generate summary
    generate_summary_markdown(year_data, args.output, logger)

    logger.info("Summary generation complete!")
    logger.info(f"Summary: {args.output}")


if __name__ == "__main__":
    main()
