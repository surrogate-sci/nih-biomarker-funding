#!/usr/bin/env python3
"""
Batch processor for NIH ExPORTER biomarker filtering across multiple fiscal years.

This script automates:
1. Downloading NIH ExPORTER CSV files by fiscal year
2. Filtering each year for biomarker-related projects
3. Combining results into a unified dataset
4. Generating summary statistics

Usage:
    # Process fiscal years 2020-2024
    python3 scripts/process_all_years.py --start-year 2020 --end-year 2024

    # Process with custom output location
    python3 scripts/process_all_years.py --start-year 2020 --end-year 2024 --output data/filtered/biomarker_2020-2024.csv

    # Skip download if files already exist locally
    python3 scripts/process_all_years.py --start-year 2020 --end-year 2024 --skip-download
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


BIOMARKER_TERMS = [
    "clinical marker",
    "biomarker",
    "surrogate endpoint",
    "intermediate outcome",
    "endpoints",
    "endophenotype",
    "genetic marker",
    "genomics",
    "omics",
    "imaging",
    "imaging marker",
]


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
    logger.info(f"Filtering FY{year} for biomarker projects...")
    filter_script = Path(__file__).parent / "filter_biomarker_projects.py"

    cmd = [
        "python3",
        str(filter_script),
        "--input-csv", str(csv_path),
        "--output", str(filtered_path),
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
    combined_stats: Dict,
    output_path: Path,
    logger: logging.Logger,
) -> None:
    """Generate a markdown summary report of the processing."""
    report_path = output_path.parent / "PROCESSING_REPORT.md"

    logger.info(f"Generating summary report: {report_path}")

    with open(report_path, "w") as f:
        f.write("# NIH Biomarker Funding Analysis - Processing Report\n\n")
        f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall statistics
        f.write("## Overall Statistics\n\n")
        f.write(f"- **Total Records**: {combined_stats['total_records']:,}\n")
        f.write(f"- **Unique Projects**: {combined_stats['unique_projects']:,}\n")
        f.write(f"- **Total Funding**: ${combined_stats['total_funding']:,.0f}\n")
        f.write(f"- **Year Range**: {combined_stats['year_range']}\n")
        f.write(f"- **Combined Dataset Size**: {combined_stats['file_size_mb']:.1f} MB\n\n")

        # Per-year breakdown
        f.write("## Per-Year Processing Results\n\n")
        f.write("| Year | Status | Matched | Total Scanned | Match Rate |\n")
        f.write("|------|--------|---------|---------------|------------|\n")

        for stats in sorted(year_stats, key=lambda x: x['year']):
            if stats['success']:
                match_rate = (stats['matched_projects'] / stats['total_projects'] * 100) if stats['total_projects'] > 0 else 0
                f.write(f"| {stats['year']} | ✓ | {stats['matched_projects']:,} | {stats['total_projects']:,} | {match_rate:.1f}% |\n")
            else:
                f.write(f"| {stats['year']} | ✗ | - | - | Error: {stats.get('error', 'Unknown')} |\n")

        f.write("\n## Search Terms Used\n\n")
        for i, term in enumerate(BIOMARKER_TERMS, 1):
            f.write(f"{i}. {term}\n")

        f.write("\n## Data Structure\n\n")
        f.write("- **Deduplication Key**: (APPLICATION_ID, FY)\n")
        f.write("- **Search Columns**: PROJECT_TITLE, PROJECT_TERMS, ABSTRACT_TEXT\n")
        f.write("- **Search Logic**: OR across all terms, OR across all columns\n")
        f.write("- **Case Sensitivity**: Case-insensitive matching\n\n")

        f.write("## Multi-Year Funding Preservation\n\n")
        f.write("This dataset preserves yearly funding records for multi-year projects.\n")
        f.write("Each project may appear multiple times (once per fiscal year) with that year's funding in TOTAL_COST.\n\n")
        f.write("To calculate total project funding:\n")
        f.write("```python\n")
        f.write("import pandas as pd\n")
        f.write("df = pd.read_csv('biomarker_combined.csv')\n")
        f.write("project_totals = df.groupby('CORE_PROJECT_NUM')['TOTAL_COST'].sum()\n")
        f.write("```\n")

    logger.info(f"Summary report saved to {report_path}")


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
        "--output",
        type=Path,
        default=None,
        help="Output path for combined CSV (default: data/filtered/biomarker_YYYY-YYYY.csv)",
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

    # Determine output path
    if args.output is None:
        args.output = args.filtered_dir / f"biomarker_{args.start_year}-{args.end_year}.csv"

    logger.info(f"Processing fiscal years {args.start_year} through {args.end_year}")
    logger.info(f"Raw data directory: {args.raw_dir}")
    logger.info(f"Filtered data directory: {args.filtered_dir}")
    logger.info(f"Combined output: {args.output}")

    # Process each fiscal year
    years = range(args.start_year, args.end_year + 1)
    year_stats = []
    filtered_paths = []

    for year in years:
        stats = process_fiscal_year(
            year=year,
            raw_dir=args.raw_dir,
            filtered_dir=args.filtered_dir,
            logger=logger,
            skip_download=args.skip_download,
            verbose=args.verbose,
        )
        year_stats.append(stats)

        if stats['success']:
            filtered_paths.append(stats['filtered_path'])

    # Check if any years succeeded
    successful_years = [s for s in year_stats if s['success']]
    if not successful_years:
        logger.error("No fiscal years were successfully processed!")
        sys.exit(1)

    logger.info(f"Successfully processed {len(successful_years)}/{len(years)} fiscal years")

    # Combine filtered years
    combined_stats = combine_filtered_years(
        filtered_paths=filtered_paths,
        output_path=args.output,
        logger=logger,
    )

    # Generate summary report
    generate_summary_report(
        year_stats=year_stats,
        combined_stats=combined_stats,
        output_path=args.output,
        logger=logger,
    )

    logger.info("Processing complete!")
    logger.info(f"Combined dataset: {args.output}")
    logger.info(f"Summary report: {args.output.parent / 'PROCESSING_REPORT.md'}")


if __name__ == "__main__":
    main()
