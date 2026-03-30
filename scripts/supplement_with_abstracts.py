#!/usr/bin/env python3
"""
Supplement keyword-filtered grants with abstract-text matches.

For each fiscal year, loads abstracts from RePORTER zip files, runs expanded
keyword search on ABSTRACT_TEXT, and writes grants that match in abstract but
NOT in the existing keyword filter to separate per-year CSVs.

The original biomarker_FY{year}.csv files are NEVER modified.
"""

import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

from scripts.abstract_loader import load_abstracts_for_year
from scripts.keyword_terms import (
    CORE_BIOMARKER_TERMS,
    EXPANDED_BIOMARKER_TERMS,
    contains_biomarker_terms,
)


def find_new_grants_from_abstracts(
    abstracts: dict[str, str],
    existing_ids: set[str],
    expanded_terms: list[str] | None = None,
    core_terms: list[str] | None = None,
) -> dict[str, dict]:
    """Identify grants matching keyword search in abstract text that aren't already filtered.

    Parameters
    ----------
    abstracts : dict
        Mapping APPLICATION_ID -> ABSTRACT_TEXT.
    existing_ids : set
        APPLICATION_IDs already in the keyword-filtered set.
    expanded_terms : list, optional
        Expanded keyword terms for matching. Defaults to EXPANDED_BIOMARKER_TERMS.
    core_terms : list, optional
        Core keyword terms for EXPLICIT_BIOMARKER flag. Defaults to CORE_BIOMARKER_TERMS.

    Returns
    -------
    dict mapping APPLICATION_ID -> {"EXPLICIT_BIOMARKER": "TRUE"/"FALSE"}
        Only includes grants that match expanded terms in abstract AND are not
        in existing_ids.
    """
    if expanded_terms is None:
        expanded_terms = EXPANDED_BIOMARKER_TERMS
    if core_terms is None:
        core_terms = CORE_BIOMARKER_TERMS

    new_grants: dict[str, dict] = {}

    for app_id, abstract_text in abstracts.items():
        # Skip grants already in keyword filter
        if app_id in existing_ids:
            continue

        # Skip empty/whitespace-only abstracts
        if not abstract_text or not abstract_text.strip():
            continue

        # Check expanded terms on abstract text
        if not contains_biomarker_terms(abstract_text, expanded_terms):
            continue

        # Check core terms for EXPLICIT_BIOMARKER flag
        is_explicit = contains_biomarker_terms(abstract_text, core_terms)

        new_grants[app_id] = {
            "EXPLICIT_BIOMARKER": "TRUE" if is_explicit else "FALSE",
        }

    return new_grants


def assign_match_source(
    app_id: str,
    in_keyword_filter: bool,
    abstract_text: str,
    expanded_terms: list[str] | None = None,
) -> str | None:
    """Determine MATCH_SOURCE for a grant.

    Parameters
    ----------
    app_id : str
        APPLICATION_ID (unused in logic, included for API consistency).
    in_keyword_filter : bool
        Whether this grant appears in the keyword-filtered set.
    abstract_text : str
        The grant's abstract text.
    expanded_terms : list, optional
        Expanded keyword terms for matching. Defaults to EXPANDED_BIOMARKER_TERMS.

    Returns
    -------
    str or None
        "keywords_only" — in keyword filter, no abstract match
        "abstract_only" — not in keyword filter, abstract matches
        "keyword_abstract" — both keyword filter and abstract match
        None — neither (should not appear in any output)
    """
    if expanded_terms is None:
        expanded_terms = EXPANDED_BIOMARKER_TERMS

    has_abstract_match = bool(
        abstract_text and contains_biomarker_terms(abstract_text, expanded_terms)
    )

    if in_keyword_filter and has_abstract_match:
        return "keyword_abstract"
    elif in_keyword_filter:
        return "keywords_only"
    elif has_abstract_match:
        return "abstract_only"
    else:
        return None


def load_existing_ids(filtered_csv: Path) -> set[str]:
    """Load APPLICATION_IDs from an existing keyword-filtered CSV.

    Returns empty set if the file does not exist.
    """
    if not filtered_csv.exists():
        return set()

    ids: set[str] = set()
    with open(filtered_csv, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            app_id = row.get("APPLICATION_ID", "").strip()
            if app_id:
                ids.add(app_id)
    return ids


def get_filtered_columns(filtered_dir: Path) -> list[str] | None:
    """Read column names from an existing filtered CSV to ensure output consistency.

    Scans filtered_dir for any biomarker_FY*.csv and returns its fieldnames.
    Returns None if no file is found.
    """
    for f in sorted(filtered_dir.glob("biomarker_FY*.csv")):
        with open(f, "r", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames:
                return list(reader.fieldnames)
    return None


def load_raw_project_rows(
    raw_dir: Path, year: int, app_ids: set[str]
) -> dict[str, dict]:
    """Load full project metadata rows from raw RePORTER project CSV/zip.

    Tries unzipped CSV first, then zip file.

    Parameters
    ----------
    raw_dir : Path
        Directory containing RePORTER_PRJ_C_FY{year}.csv or .zip files.
    year : int
        Fiscal year.
    app_ids : set
        APPLICATION_IDs to extract.

    Returns
    -------
    dict mapping APPLICATION_ID -> row dict (all columns from raw CSV).
    """
    if not app_ids:
        return {}

    # Try unzipped CSV first
    csv_path = Path(raw_dir) / f"RePORTER_PRJ_C_FY{year}.csv"
    if csv_path.exists():
        return _read_project_rows_from_csv(csv_path, app_ids)

    # Try zip file
    zip_path = Path(raw_dir) / f"RePORTER_PRJ_C_FY{year}.zip"
    if zip_path.exists():
        return _read_project_rows_from_zip(zip_path, app_ids)

    print(f"  WARNING: raw project file not found for FY{year} in {raw_dir}")
    return {}


def _read_project_rows_from_csv(csv_path: Path, app_ids: set[str]) -> dict[str, dict]:
    """Read matching rows from an unzipped project CSV."""
    rows: dict[str, dict] = {}
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            app_id = row.get("APPLICATION_ID", "").strip()
            if app_id in app_ids:
                rows[app_id] = dict(row)
    return rows


def _read_project_rows_from_zip(zip_path: Path, app_ids: set[str]) -> dict[str, dict]:
    """Read matching rows from a zipped project CSV."""
    rows: dict[str, dict] = {}
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            print(f"  WARNING: no CSV found inside {zip_path}")
            return {}

        with zf.open(csv_names[0]) as raw:
            text_wrapper = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_wrapper)
            for row in reader:
                app_id = row.get("APPLICATION_ID", "").strip()
                if app_id in app_ids:
                    rows[app_id] = dict(row)
    return rows


def process_year(
    year: int,
    abs_dir: Path,
    raw_dir: Path,
    filtered_dir: Path,
    output_columns: list[str],
    dry_run: bool = False,
) -> dict[str, int]:
    """Process a single fiscal year: find abstract-only matches and write output.

    Parameters
    ----------
    year : int
        Fiscal year to process.
    abs_dir : Path
        Directory containing RePORTER abstract zip files.
    raw_dir : Path
        Directory containing raw RePORTER project CSVs/zips.
    filtered_dir : Path
        Directory containing keyword-filtered biomarker_FY{year}.csv files.
    output_columns : list
        Column names for the output CSV (must include EXPLICIT_BIOMARKER).
    dry_run : bool
        If True, report counts without writing files.

    Returns
    -------
    dict with keys: year, existing_count, abstract_count, new_count, written.
    """
    stats = {
        "year": year,
        "existing_count": 0,
        "abstract_count": 0,
        "new_count": 0,
        "written": 0,
    }

    # Step 1: Load existing keyword-filtered IDs
    filtered_csv = filtered_dir / f"biomarker_FY{year}.csv"
    existing_ids = load_existing_ids(filtered_csv)
    stats["existing_count"] = len(existing_ids)

    # Step 2: Load all abstracts for this year
    abstracts = load_abstracts_for_year(year, abs_dir)
    stats["abstract_count"] = len(abstracts)

    if not abstracts:
        print(f"  FY{year}: no abstracts loaded, skipping")
        return stats

    # Step 3: Find new grants from abstract keyword matches
    new_grants = find_new_grants_from_abstracts(abstracts, existing_ids)
    stats["new_count"] = len(new_grants)

    print(
        f"  FY{year}: {stats['existing_count']:,} keyword-filtered, "
        f"{stats['abstract_count']:,} abstracts, "
        f"{stats['new_count']:,} new abstract-only matches"
    )

    if dry_run or not new_grants:
        return stats

    # Step 4: Load full metadata for new grants from raw project CSVs
    new_ids = set(new_grants.keys())
    project_rows = load_raw_project_rows(raw_dir, year, new_ids)

    # Step 5: Write output CSV
    output_path = filtered_dir / f"biomarker_abstract_FY{year}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_columns)
        writer.writeheader()

        for app_id in sorted(new_grants.keys()):
            if app_id not in project_rows:
                continue  # No metadata available

            row = project_rows[app_id]
            # Ensure EXPLICIT_BIOMARKER is set from our analysis
            row["EXPLICIT_BIOMARKER"] = new_grants[app_id]["EXPLICIT_BIOMARKER"]

            # Write only the columns we expect
            output_row = {col: row.get(col, "") for col in output_columns}
            writer.writerow(output_row)
            stats["written"] += 1

    print(f"  FY{year}: wrote {stats['written']:,} rows to {output_path}")
    return stats


# Default columns matching the existing filtered CSV format
DEFAULT_COLUMNS = [
    "APPLICATION_ID",
    "ACTIVITY",
    "ADMINISTERING_IC",
    "APPLICATION_TYPE",
    "ARRA_FUNDED",
    "AWARD_NOTICE_DATE",
    "BUDGET_START",
    "BUDGET_END",
    "CFDA_CODE",
    "CORE_PROJECT_NUM",
    "ED_INST_TYPE",
    "OPPORTUNITY NUMBER",
    "FULL_PROJECT_NUM",
    "FUNDING_ICs",
    "FUNDING_MECHANISM",
    "FY",
    "IC_NAME",
    "NIH_SPENDING_CATS",
    "ORG_CITY",
    "ORG_COUNTRY",
    "ORG_DEPT",
    "ORG_DISTRICT",
    "ORG_DUNS",
    "ORG_FIPS",
    "ORG_IPF_CODE",
    "ORG_NAME",
    "ORG_STATE",
    "ORG_ZIPCODE",
    "PHR",
    "PI_IDS",
    "PI_NAMEs",
    "PROGRAM_OFFICER_NAME",
    "PROJECT_START",
    "PROJECT_END",
    "PROJECT_TERMS",
    "PROJECT_TITLE",
    "SERIAL_NUMBER",
    "STUDY_SECTION",
    "STUDY_SECTION_NAME",
    "SUBPROJECT_ID",
    "SUFFIX",
    "SUPPORT_YEAR",
    "DIRECT_COST_AMT",
    "INDIRECT_COST_AMT",
    "TOTAL_COST",
    "TOTAL_COST_SUB_PROJECT",
    "EXPLICIT_BIOMARKER",
]


def main():
    parser = argparse.ArgumentParser(
        description="Supplement keyword-filtered grants with abstract-text matches.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all years
  %(prog)s --abs-dir ~/Downloads --raw-dir ~/Downloads

  # Dry run for specific years
  %(prog)s --years 2005 2006 --dry-run

  # Custom directories
  %(prog)s --abs-dir /data/abstracts --raw-dir /data/projects --filtered-dir data/filtered/
        """,
    )

    parser.add_argument(
        "--abs-dir",
        type=Path,
        default=Path.home() / "Downloads",
        help="Directory containing RePORTER abstract zip files (default: ~/Downloads)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path.home() / "Downloads",
        help="Directory containing raw RePORTER project CSVs (default: ~/Downloads)",
    )
    parser.add_argument(
        "--filtered-dir",
        type=Path,
        default=Path("data/filtered"),
        help="Directory containing keyword-filtered CSVs (default: data/filtered/)",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(range(2004, 2025)),
        help="Fiscal years to process (default: 2004-2024)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be found without writing files",
    )

    args = parser.parse_args()

    # Determine output columns from existing filtered files, or use defaults
    output_columns = get_filtered_columns(args.filtered_dir) or DEFAULT_COLUMNS

    # Ensure EXPLICIT_BIOMARKER is in the column list
    if "EXPLICIT_BIOMARKER" not in output_columns:
        output_columns.append("EXPLICIT_BIOMARKER")

    print(f"Processing {len(args.years)} fiscal years")
    print(f"  Abstract dir: {args.abs_dir}")
    print(f"  Raw project dir: {args.raw_dir}")
    print(f"  Filtered dir: {args.filtered_dir}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Output columns: {len(output_columns)}")
    print()

    total_new = 0
    total_written = 0

    for year in sorted(args.years):
        stats = process_year(
            year=year,
            abs_dir=args.abs_dir,
            raw_dir=args.raw_dir,
            filtered_dir=args.filtered_dir,
            output_columns=output_columns,
            dry_run=args.dry_run,
        )
        total_new += stats["new_count"]
        total_written += stats["written"]

    print()
    print(f"Total new abstract-only matches: {total_new:,}")
    if not args.dry_run:
        print(f"Total rows written: {total_written:,}")


if __name__ == "__main__":
    main()
