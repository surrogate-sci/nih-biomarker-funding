#!/usr/bin/env python3
"""
Download and filter NIH ExPORTER data for biomarker-related projects.

This script downloads NIH ExPORTER CSV files and filters them for projects containing
biomarker-related terminology in their project titles and terms.
"""

import argparse
import csv
import logging
import re
import sys
import time
from pathlib import Path
from typing import Set, Dict, List
from urllib.parse import urljoin
import requests


# Biomarker-related search terms (case-insensitive)
# Use '+' for AND conditions (e.g., "clinical+omics" requires both words present)
BIOMARKER_TERMS = [
    "clinical marker",
    "biomarker",
    "digital biomarker",
    "surrogate endpoint",
    "intermediate outcome",
    "endophenotype",
    "genetic marker",
    "clinical+omics",  # Requires both "clinical" AND "omics"
    "clinical+imaging",  # Requires both "clinical" AND "imaging"
    "imaging marker",
]


# NIH ExPORTER CSV download base URL
# Note: SciOP mirrors NIH ExPORTER data - we'll use the official source
NIH_EXPORTER_BASE_URL = "https://exporter.nih.gov/CSVs/final/"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def download_file(url: str, output_path: Path, logger: logging.Logger, max_retries: int = 4) -> bool:
    """
    Download a file with exponential backoff retry logic.

    Args:
        url: URL to download
        output_path: Path to save the file
        logger: Logger instance
        max_retries: Maximum number of retry attempts

    Returns:
        True if download successful, False otherwise
    """
    backoff_times = [2, 4, 8, 16]  # Exponential backoff in seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading {url} (attempt {attempt + 1}/{max_retries})...")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))

            # Download with progress
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                downloaded = 0
                chunk_size = 8192
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            logger.debug(f"Progress: {percent:.1f}%")

            logger.info(f"Successfully downloaded to {output_path}")
            return True

        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = backoff_times[attempt]
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to download {url} after {max_retries} attempts")
                return False

    return False


def contains_biomarker_terms(text: str, terms: List[str]) -> bool:
    """
    Check if text contains any of the biomarker terms (case-insensitive).

    Supports AND conditions using '+' separator (e.g., "clinical+omics" requires both words).

    Args:
        text: Text to search
        terms: List of search terms (single terms or AND conditions with '+')

    Returns:
        True if any term (or AND condition) is found, False otherwise
    """
    if not text:
        return False

    text_lower = text.lower()

    for term in terms:
        if '+' in term:
            # AND condition: all parts must be present
            parts = [part.strip().lower() for part in term.split('+')]
            if all(part in text_lower for part in parts):
                return True
        else:
            # Single term: just check if present
            if term.lower() in text_lower:
                return True

    return False


def filter_projects_csv(
    input_path: Path,
    output_path: Path,
    logger: logging.Logger,
    search_terms: List[str],
    text_columns: List[str] = None,
    project_id_column: str = "APPLICATION_ID",
    fy_column: str = "FY",
) -> Dict[str, int]:
    """
    Filter a projects CSV file for biomarker-related terms.

    Args:
        input_path: Path to input CSV
        output_path: Path to output CSV
        logger: Logger instance
        search_terms: Terms to search for
        text_columns: Columns to search (default: PROJECT_TITLE, PROJECT_TERMS)
        project_id_column: Column to use for deduplication (default: APPLICATION_ID)
        fy_column: Fiscal year column for multi-year deduplication (default: FY)

    Returns:
        Statistics dictionary
    """
    if text_columns is None:
        text_columns = ["PROJECT_TITLE", "PROJECT_TERMS"]

    logger.info(f"Filtering {input_path}...")
    logger.info(f"Searching columns: {', '.join(text_columns)}")
    logger.info(f"Search terms: {', '.join(search_terms)}")
    logger.info(f"Deduplication key: ({project_id_column}, {fy_column})")

    stats = {
        "total_rows": 0,
        "matched_rows": 0,
        "unique_projects": 0,
        "duplicates_removed": 0,
    }

    # Track unique (APPLICATION_ID, FY) combinations to preserve yearly funding
    seen_records: Set = set()

    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as infile:
            reader = csv.DictReader(infile)

            # Validate columns exist
            if reader.fieldnames is None:
                logger.error("CSV file has no headers")
                return stats

            available_text_cols = [col for col in text_columns if col in reader.fieldnames]
            if not available_text_cols:
                logger.warning(f"None of the specified text columns found. Available: {reader.fieldnames}")
                logger.info("Will search all text columns")
                available_text_cols = list(reader.fieldnames)
            else:
                logger.info(f"Found columns: {', '.join(available_text_cols)}")

            if project_id_column not in reader.fieldnames:
                logger.error(f"Project ID column '{project_id_column}' not found in CSV")
                return stats

            # Write filtered output
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
                writer.writeheader()

                for row in reader:
                    stats["total_rows"] += 1

                    # Check if any text column contains biomarker terms
                    has_match = False
                    for col in available_text_cols:
                        if contains_biomarker_terms(row.get(col, ""), search_terms):
                            has_match = True
                            break

                    if has_match:
                        stats["matched_rows"] += 1

                        # Deduplicate by (APPLICATION_ID, FY) to preserve yearly funding records
                        project_id = row.get(project_id_column, "")
                        fiscal_year = row.get(fy_column, "")

                        # Create composite key to track unique project-year combinations
                        unique_key = (project_id, fiscal_year) if fiscal_year else project_id

                        if project_id and unique_key not in seen_records:
                            seen_records.add(unique_key)
                            writer.writerow(row)
                            stats["unique_projects"] += 1
                        elif project_id:
                            stats["duplicates_removed"] += 1

                    # Progress reporting
                    if stats["total_rows"] % 10000 == 0:
                        logger.info(f"Processed {stats['total_rows']:,} rows, found {stats['matched_rows']:,} matches...")

        logger.info(f"Filtering complete:")
        logger.info(f"  Total rows processed: {stats['total_rows']:,}")
        logger.info(f"  Rows matching terms: {stats['matched_rows']:,}")
        logger.info(f"  Unique project-year records kept: {stats['unique_projects']:,}")
        logger.info(f"  Duplicates removed: {stats['duplicates_removed']:,}")
        logger.info(f"  Output saved to: {output_path}")

    except FileNotFoundError:
        logger.error(f"Input file not found: {input_path}")
    except Exception as e:
        logger.error(f"Error filtering CSV: {e}", exc_info=True)

    return stats


def filter_abstracts_csv(
    projects_path: Path,
    abstracts_path: Path,
    output_path: Path,
    logger: logging.Logger,
    search_terms: List[str],
) -> Dict[str, int]:
    """
    Filter abstracts CSV by joining with already-filtered projects.

    Args:
        projects_path: Path to filtered projects CSV
        abstracts_path: Path to input abstracts CSV
        output_path: Path to output abstracts CSV
        logger: Logger instance
        search_terms: Additional terms to search in abstract text

    Returns:
        Statistics dictionary
    """
    logger.info(f"Loading filtered project IDs from {projects_path}...")

    # Load project IDs from filtered projects
    project_ids: Set[str] = set()
    try:
        with open(projects_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "APPLICATION_ID" in row:
                    project_ids.add(row["APPLICATION_ID"])
    except Exception as e:
        logger.error(f"Error reading projects file: {e}")
        return {"total_rows": 0, "matched_rows": 0}

    logger.info(f"Loaded {len(project_ids):,} project IDs")
    logger.info(f"Filtering abstracts from {abstracts_path}...")

    stats = {"total_rows": 0, "matched_rows": 0, "additional_matches": 0}

    try:
        with open(abstracts_path, 'r', encoding='utf-8', errors='ignore') as infile:
            reader = csv.DictReader(infile)

            if reader.fieldnames is None:
                logger.error("Abstracts CSV has no headers")
                return stats

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
                writer.writeheader()

                for row in reader:
                    stats["total_rows"] += 1

                    app_id = row.get("APPLICATION_ID", "")

                    # Keep if in filtered projects OR contains biomarker terms
                    in_projects = app_id in project_ids
                    has_term = contains_biomarker_terms(
                        row.get("ABSTRACT_TEXT", ""), search_terms
                    )

                    if in_projects or has_term:
                        writer.writerow(row)
                        stats["matched_rows"] += 1

                        if has_term and not in_projects:
                            stats["additional_matches"] += 1

                    if stats["total_rows"] % 10000 == 0:
                        logger.info(f"Processed {stats['total_rows']:,} abstracts...")

        logger.info(f"Abstract filtering complete:")
        logger.info(f"  Total abstracts: {stats['total_rows']:,}")
        logger.info(f"  Abstracts kept: {stats['matched_rows']:,}")
        logger.info(f"  Additional matches from abstract text: {stats['additional_matches']:,}")

    except FileNotFoundError:
        logger.error(f"Abstracts file not found: {abstracts_path}")
    except Exception as e:
        logger.error(f"Error filtering abstracts: {e}", exc_info=True)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Download and filter NIH Reporter data for biomarker-related projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Filter existing local CSV file
  %(prog)s --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv --output data/filtered/biomarker_projects_2023.csv

  # Download and filter a specific year
  %(prog)s --year 2023 --output data/filtered/biomarker_projects_2023.csv

  # Use custom search terms
  %(prog)s --input-csv data/raw/projects.csv --terms "biomarker" "diagnostic marker" --output filtered.csv

  # Download projects CSV for 2023 (you'll need to specify the exact filename from NIH ExPORTER)
  %(prog)s --download-url https://exporter.nih.gov/CSVs/final/RePORTER_PRJ_C_FY2023.zip --output biomarkers_2023.csv
        """,
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-csv",
        type=Path,
        help="Path to local projects CSV file to filter",
    )
    input_group.add_argument(
        "--download-url",
        type=str,
        help="URL to download NIH ExPORTER CSV/ZIP file",
    )
    input_group.add_argument(
        "--year",
        type=int,
        help="Fiscal year to download (e.g., 2023). Will construct download URL.",
    )

    # Output options
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/filtered/biomarker_projects.csv"),
        help="Output CSV file path (default: data/filtered/biomarker_projects.csv)",
    )

    # Filtering options
    parser.add_argument(
        "--terms",
        nargs="+",
        default=BIOMARKER_TERMS,
        help=f"Search terms (default: {', '.join(BIOMARKER_TERMS)})",
    )

    parser.add_argument(
        "--columns",
        nargs="+",
        default=["PROJECT_TITLE", "PROJECT_TERMS"],
        help="Columns to search (default: PROJECT_TITLE, PROJECT_TERMS)",
    )

    parser.add_argument(
        "--id-column",
        default="APPLICATION_ID",
        help="Column name for project ID deduplication (default: APPLICATION_ID)",
    )

    # Optional abstracts filtering
    parser.add_argument(
        "--abstracts-csv",
        type=Path,
        help="Path to abstracts CSV file to filter (optional)",
    )

    parser.add_argument(
        "--abstracts-output",
        type=Path,
        help="Output path for filtered abstracts (default: same dir as --output)",
    )

    # General options
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory for downloaded files (default: data/raw)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    logger = setup_logging(args.verbose)

    # Determine input CSV path
    input_csv_path = None

    if args.input_csv:
        input_csv_path = args.input_csv
        if not input_csv_path.exists():
            logger.error(f"Input file not found: {input_csv_path}")
            sys.exit(1)

    elif args.download_url:
        # Download from URL
        filename = args.download_url.split('/')[-1]
        download_path = args.data_dir / filename

        if download_file(args.download_url, download_path, logger):
            # Handle ZIP files if needed
            if download_path.suffix == '.zip':
                logger.info("ZIP file support not yet implemented. Please extract manually.")
                logger.info(f"Extract {download_path} and re-run with --input-csv")
                sys.exit(1)
            input_csv_path = download_path
        else:
            logger.error("Download failed")
            sys.exit(1)

    elif args.year:
        # Construct URL for fiscal year
        # Note: This is a placeholder - actual NIH ExPORTER URLs may vary
        logger.warning("Year-based download is experimental.")
        logger.info(f"For accurate downloads, visit: https://reporter.nih.gov/exporter")
        logger.info(f"Download the Projects CSV for FY{args.year} manually")
        logger.info(f"Then run: {sys.argv[0]} --input-csv <downloaded-file> --output {args.output}")
        sys.exit(1)

    # Filter projects
    if input_csv_path:
        stats = filter_projects_csv(
            input_csv_path,
            args.output,
            logger,
            args.terms,
            args.columns,
            args.id_column,
        )

        # Filter abstracts if provided
        if args.abstracts_csv:
            if not args.abstracts_csv.exists():
                logger.error(f"Abstracts file not found: {args.abstracts_csv}")
            else:
                abstracts_output = args.abstracts_output or (
                    args.output.parent / f"{args.output.stem}_abstracts.csv"
                )
                filter_abstracts_csv(
                    args.output,
                    args.abstracts_csv,
                    abstracts_output,
                    logger,
                    args.terms,
                )

        if stats["unique_projects"] > 0:
            logger.info(f"✓ Success! Filtered {stats['unique_projects']:,} unique biomarker project-year records")
        else:
            logger.warning("No matching projects found. Check your search terms and input data.")


if __name__ == "__main__":
    main()
