#!/usr/bin/env python3
"""
Batch processor for NIH ExPORTER biomarker filtering across multiple fiscal years.

This script automates:
1. Downloading NIH ExPORTER CSV files by fiscal year
2. Filtering each year for biomarker-related projects
3. Generating summary statistics for each year

Usage:
    # Process fiscal years 2020-2024 with expanded term set
    python3 scripts/process_all_years.py --start-year 2020 --end-year 2024

    # Process with core term set (higher precision)
    python3 scripts/process_all_years.py --start-year 2020 --end-year 2024 --term-set core

    # Skip download if files already exist locally
    python3 scripts/process_all_years.py --start-year 2020 --end-year 2024 --skip-download

    # Use existing downloads from ~/Downloads
    python3 scripts/process_all_years.py --start-year 2004 --end-year 2023 --skip-download --raw-dir ~/Downloads
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict
import subprocess
import pandas as pd
import zipfile
import time
import requests


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging with appropriate level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def download_file(url: str, output_path: Path, logger: logging.Logger, max_retries: int = 4) -> bool:
    """Download a file with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading {url} (attempt {attempt + 1}/{max_retries})...")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and downloaded % (10 * 1024 * 1024) == 0:  # Log every 10MB
                            logger.debug(f"Downloaded {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB")

            logger.info(f"Successfully downloaded {output_path.name} ({output_path.stat().st_size / (1024*1024):.1f} MB)")
            return True

        except Exception as e:
            wait_time = 2 ** attempt
            if attempt < max_retries - 1:
                logger.warning(f"Download failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Download failed after {max_retries} attempts: {e}")
                return False

    return False


def extract_zip(zip_path: Path, extract_dir: Path, logger: logging.Logger) -> List[Path]:
    """Extract a ZIP file and return paths to extracted CSV files."""
    logger.info(f"Extracting {zip_path.name}...")
    extracted_files = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get list of CSV files in the ZIP
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]

            for csv_file in csv_files:
                extract_path = extract_dir / csv_file
                zip_ref.extract(csv_file, extract_dir)
                extracted_files.append(extract_path)
                logger.info(f"  Extracted: {csv_file} ({extract_path.stat().st_size / (1024*1024):.1f} MB)")

        return extracted_files
    except Exception as e:
        logger.error(f"Failed to extract {zip_path}: {e}")
        return []


def process_fiscal_year(
    year: int,
    raw_dir: Path,
    filtered_dir: Path,
    logger: logging.Logger,
    skip_download: bool = False,
    verbose: bool = False,
    term_set: str = "expanded",
) -> Dict[str, any]:
    """
    Process a single fiscal year: download, extract, and filter.

    Returns dict with statistics about the processing.
    """
    logger.info(f"=" * 80)
    logger.info(f"Processing fiscal year {year}...")
    logger.info(f"=" * 80)

    # Define paths
    zip_path = raw_dir / f"RePORTER_PRJ_C_FY{year}.zip"
    csv_filename = f"RePORTER_PRJ_C_FY{year}.csv"
    csv_path = raw_dir / csv_filename
    filtered_path = filtered_dir / f"biomarker_FY{year}.csv"

    # Download if needed
    if not skip_download or not csv_path.exists():
        if not csv_path.exists():
            if not zip_path.exists():
                # Download ZIP file from NIH ExPORTER
                url = f"https://exporter.nih.gov/CSVs/final/RePORTER_PRJ_C_FY{year}.zip"
                logger.info(f"Downloading FY{year} from NIH ExPORTER...")
                if not download_file(url, zip_path, logger):
                    return {
                        "year": year,
                        "success": False,
                        "error": "Download failed",
                    }
            else:
                logger.info(f"Using existing ZIP: {zip_path}")

            # Extract ZIP file
            extracted_files = extract_zip(zip_path, raw_dir, logger)
            if not extracted_files:
                return {
                    "year": year,
                    "success": False,
                    "error": "ZIP extraction failed",
                }

            # Find the projects CSV
            csv_path = next((f for f in extracted_files if "PRJ_C" in f.name), None)
            if not csv_path or not csv_path.exists():
                logger.error(f"Projects CSV not found in extracted files: {extracted_files}")
                return {
                    "year": year,
                    "success": False,
                    "error": "Projects CSV not found in ZIP",
                }
        else:
            logger.info(f"Using existing CSV: {csv_path}")
    else:
        logger.info(f"Skipping download, using existing file: {csv_path}")

    # Verify CSV exists
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return {
            "year": year,
            "success": False,
            "error": "CSV file not found",
        }

    # Filter using the existing filter script via subprocess
    logger.info(f"Filtering FY{year} for biomarker projects using '{term_set}' term set...")
    filter_script = Path(__file__).parent / "filter_biomarker_projects.py"

    cmd = [
        "python3",
        str(filter_script),
        "--input-csv", str(csv_path),
        "--output", str(filtered_path),
        "--term-set", term_set,
    ]

    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.debug(result.stdout)

        # Parse statistics from the filtered CSV
        if filtered_path.exists():
            df = pd.read_csv(filtered_path)
            matched_projects = len(df)

            # Get total from original (just read first few lines to get header)
            total_projects = sum(1 for _ in open(csv_path)) - 1  # Subtract header

            return {
                "year": year,
                "success": True,
                "filtered_path": filtered_path,
                "matched_projects": matched_projects,
                "total_projects": total_projects,
            }
        else:
            logger.error(f"Filtered output not created: {filtered_path}")
            return {
                "year": year,
                "success": False,
                "error": "Filtered output not created",
            }

    except subprocess.CalledProcessError as e:
        logger.error(f"Filter script failed: {e.stderr}")
        return {
            "year": year,
            "success": False,
            "error": f"Filter script failed: {e.stderr[:200]}",
        }
    except Exception as e:
        logger.error(f"Failed to filter FY{year}: {e}")
        return {
            "year": year,
            "success": False,
            "error": str(e),
        }


def combine_filtered_years(
    filtered_paths: List[Path],
    output_path: Path,
    logger: logging.Logger,
) -> Dict[str, any]:
    """
    Combine multiple filtered year CSVs into a unified dataset.

    Preserves multi-year funding by keeping (APPLICATION_ID, FY) records intact.
    """
    logger.info(f"Combining {len(filtered_paths)} filtered year files...")

    dfs = []
    for path in filtered_paths:
        logger.info(f"  Reading {path.name}...")
        df = pd.read_csv(path)
        dfs.append(df)

    # Concatenate all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)

    # Deduplicate by (APPLICATION_ID, FY) to preserve yearly funding
    logger.info("Deduplicating by (APPLICATION_ID, FY)...")
    initial_count = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=["APPLICATION_ID", "FY"])
    final_count = len(combined_df)
    duplicates_removed = initial_count - final_count

    # Save combined dataset
    logger.info(f"Saving combined dataset to {output_path}...")
    combined_df.to_csv(output_path, index=False)

    # Calculate statistics
    total_funding = combined_df["TOTAL_COST"].sum()
    unique_projects = combined_df["CORE_PROJECT_NUM"].nunique()
    year_range = f"{combined_df['FY'].min()}-{combined_df['FY'].max()}"

    stats = {
        "total_records": final_count,
        "duplicates_removed": duplicates_removed,
        "unique_projects": unique_projects,
        "total_funding": total_funding,
        "year_range": year_range,
        "file_size_mb": output_path.stat().st_size / (1024 * 1024),
    }

    logger.info(f"Combined dataset statistics:")
    logger.info(f"  Total records: {final_count:,}")
    logger.info(f"  Unique projects (CORE_PROJECT_NUM): {unique_projects:,}")
    logger.info(f"  Total funding: ${total_funding:,.0f}")
    logger.info(f"  Year range: {year_range}")
    logger.info(f"  File size: {stats['file_size_mb']:.1f} MB")

    return stats


def generate_summary_report(
    year_stats: List[Dict],
    filtered_dir: Path,
    term_set: str,
    logger: logging.Logger,
) -> None:
    """Generate a markdown summary report of the processing."""
    report_path = filtered_dir / "SUMMARY.md"

    logger.info(f"Generating summary: {report_path}")

    with open(report_path, "w") as f:
        f.write("# NIH Biomarker Funding Analysis - Processing Report\n\n")
        f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Combined table with projects and funding
        f.write("## Per-Year Results\n\n")
        f.write("| Year | Biomarker Relevant Spending | Explicit Biomarker Spending | Matched Projects | Total Scanned |\n")
        f.write("|------|------------------------------|------------------------------|------------------|---------------|\n")

        total_matched = 0
        total_explicit = 0
        total_scanned = 0
        total_funding = 0
        total_explicit_funding = 0

        for stats in sorted(year_stats, key=lambda x: x['year']):
            if stats['success']:
                # Read data and calculate metrics
                if term_set == "expanded" and stats.get('filtered_path'):
                    try:
                        df = pd.read_csv(stats['filtered_path'])

                        # Count explicit biomarker matches
                        explicit_count = ((df['EXPLICIT_BIOMARKER'] == True) | (df['EXPLICIT_BIOMARKER'] == 'TRUE')).sum()
                        total_explicit += explicit_count

                        # Calculate funding
                        df['TOTAL_COST_NUM'] = pd.to_numeric(df['TOTAL_COST'], errors='coerce')
                        year_funding = df['TOTAL_COST_NUM'].sum()
                        year_explicit_funding = df[df['EXPLICIT_BIOMARKER'] == True]['TOTAL_COST_NUM'].sum()
                        total_funding += year_funding
                        total_explicit_funding += year_explicit_funding

                        f.write(f"| {stats['year']} | ${year_funding/1e9:.2f}B | ${year_explicit_funding/1e9:.2f}B | {stats['matched_projects']:,} | {stats['total_projects']:,} |\n")
                    except Exception as e:
                        logger.warning(f"Could not read data from FY{stats['year']}: {e}")
                        f.write(f"| {stats['year']} | - | - | {stats['matched_projects']:,} | {stats['total_projects']:,} |\n")
                else:
                    f.write(f"| {stats['year']} | - | - | {stats['matched_projects']:,} | {stats['total_projects']:,} |\n")

                total_matched += stats['matched_projects']
                total_scanned += stats['total_projects']
            else:
                f.write(f"| {stats['year']} | Error | Error | Error | Error |\n")

        # Add column definitions
        f.write("\n### Column Definitions\n\n")
        f.write("- **Year**: NIH fiscal year\n")
        f.write("- **Biomarker Relevant Spending**: Total TOTAL_COST for all matched projects\n")
        f.write("- **Explicit Biomarker Spending**: Total TOTAL_COST for projects matching core biomarker terms\n")
        f.write("- **Matched Projects**: Projects where PROJECT_TITLE or PROJECT_TERMS fields contain any biomarker search term (case-insensitive, with AND logic for terms containing '+')\n")
        f.write("- **Total Scanned**: Total projects examined in NIH ExPORTER RePORTER_PRJ_C_FY{year}.csv file\n")

        # Add search terms
        f.write("\n### Search Terms Used\n\n")
        f.write("**Core biomarker terms (4):**\n")
        f.write("- biomarker, clinical marker, surrogate endpoint, imaging marker\n\n")
        f.write("**Expanded biomarker terms (10):**\n")
        f.write("- biomarker, clinical marker, surrogate endpoint, imaging marker, digital biomarker, intermediate outcome, endophenotype, genetic marker, clinical+omics, clinical+imaging\n")

        f.write("\n## Overall Statistics\n\n")
        f.write("### Projects\n")
        f.write(f"- **Total Matched Projects (Expanded)**: {total_matched:,}\n")
        if term_set == "expanded" and total_explicit > 0:
            f.write(f"- **Explicit Biomarker Projects (Core)**: {total_explicit:,}\n")
            f.write(f"- **Other Biomarker-Related Projects**: {total_matched - total_explicit:,}\n")
        f.write(f"- **Total Scanned Projects**: {total_scanned:,}\n")
        f.write(f"- **Overall Match Rate**: {(total_matched/total_scanned*100):.1f}%\n")
        if term_set == "expanded" and total_explicit > 0:
            f.write(f"- **Explicit Biomarker Rate**: {(total_explicit/total_scanned*100):.1f}%\n")

        if term_set == "expanded" and total_funding > 0:
            f.write("\n### Funding\n")
            f.write(f"- **Biomarker Relevant Spending**: ${total_funding/1e9:.2f}B\n")
            f.write(f"- **Explicit Biomarker Spending**: ${total_explicit_funding/1e9:.2f}B ({total_explicit_funding/total_funding*100:.1f}%)\n")

        f.write(f"\n### Processing\n")
        f.write(f"- **Term Set Used**: {term_set}\n")
        f.write(f"- **Years Processed**: {len([s for s in year_stats if s['success']])}/{len(year_stats)}\n\n")

        f.write("\n## Output Files\n\n")
        f.write("Individual year files saved to `data/filtered/`:\n")
        for stats in sorted(year_stats, key=lambda x: x['year']):
            if stats['success']:
                f.write(f"- `biomarker_FY{stats['year']}.csv`")
                if term_set == "expanded":
                    f.write(" (includes `EXPLICIT_BIOMARKER` column)")
                f.write("\n")

        f.write("\n## Data Structure\n\n")
        f.write("- **Deduplication Key**: (APPLICATION_ID, FY)\n")
        f.write("- **Search Columns**: PROJECT_TITLE, PROJECT_TERMS\n")
        f.write("- **Search Logic**: OR across all terms, AND logic for terms with '+'\n")
        f.write("- **Case Sensitivity**: Case-insensitive matching\n")
        if term_set == "expanded":
            f.write("- **EXPLICIT_BIOMARKER Column**: TRUE for projects matching core terms (biomarker, clinical marker, surrogate endpoint, imaging marker)\n")
        f.write("\n")

    logger.info(f"Summary saved to {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch process NIH ExPORTER data for biomarker projects across multiple fiscal years"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        required=True,
        help="First fiscal year to process (e.g., 2020)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        required=True,
        help="Last fiscal year to process (e.g., 2024)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory for raw downloaded files (default: data/raw)",
    )
    parser.add_argument(
        "--filtered-dir",
        type=Path,
        default=Path("data/filtered"),
        help="Directory for filtered output files (default: data/filtered)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download if CSV files already exist locally",
    )
    parser.add_argument(
        "--term-set",
        choices=["core", "expanded"],
        default="expanded",
        help="Biomarker term set: 'core' (4 terms) or 'expanded' (10 terms, includes core) (default: expanded). When using expanded, both counts are tracked.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup
    logger = setup_logging(args.verbose)

    # Validate year range
    if args.start_year > args.end_year:
        logger.error("Start year must be <= end year")
        sys.exit(1)

    # Create directories
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.filtered_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Processing fiscal years {args.start_year} through {args.end_year}")
    logger.info(f"Term set: {args.term_set}")
    logger.info(f"Raw data directory: {args.raw_dir}")
    logger.info(f"Filtered data directory: {args.filtered_dir}")

    # Process each fiscal year
    years = range(args.start_year, args.end_year + 1)
    year_stats = []

    for year in years:
        stats = process_fiscal_year(
            year=year,
            raw_dir=args.raw_dir,
            filtered_dir=args.filtered_dir,
            logger=logger,
            skip_download=args.skip_download,
            verbose=args.verbose,
            term_set=args.term_set,
        )
        year_stats.append(stats)

    # Check if any years succeeded
    successful_years = [s for s in year_stats if s['success']]
    if not successful_years:
        logger.error("No fiscal years were successfully processed!")
        sys.exit(1)

    logger.info(f"Successfully processed {len(successful_years)}/{len(years)} fiscal years")

    # Generate summary report
    generate_summary_report(
        year_stats=year_stats,
        filtered_dir=args.filtered_dir,
        term_set=args.term_set,
        logger=logger,
    )

    logger.info("Processing complete!")
    logger.info(f"Individual year files saved to: {args.filtered_dir}")
    logger.info(f"Summary: {args.filtered_dir / 'SUMMARY.md'}")


if __name__ == "__main__":
    main()
