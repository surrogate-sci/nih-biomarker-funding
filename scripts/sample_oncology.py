"""
Sample NCI/oncology biomarker grants with stratified sampling by fiscal year.

Filters the unified dataset to ADMINISTERING_IC == 'CA', samples N per year,
joins abstracts from RePORTER zip files, outputs a ready-to-grade CSV.

Usage:
    python3 scripts/sample_oncology.py
    python3 scripts/sample_oncology.py --n 100 --seed 42
    python3 scripts/sample_oncology.py --n 5 --output /tmp/test_sample.csv  # smoke test
"""

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

# Add parent to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.abstract_loader import load_abstracts_for_year

# FY2016 abstracts are missing from disk
SKIP_YEARS = {2016}

OUTPUT_COLUMNS = [
    "FY",
    "APPLICATION_ID",
    "ADMINISTERING_IC",
    "IC_NAME",
    "ACTIVITY",
    "TOTAL_COST",
    "EXPLICIT_BIOMARKER",
    "PROJECT_TITLE",
    "ABSTRACT_TEXT",
    "HAS_ABSTRACT",
]


def load_nci_grants(csv_path: Path) -> list[dict]:
    """Load unified dataset and filter to NCI grants (ADMINISTERING_IC == 'CA')."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("ADMINISTERING_IC", "").strip() == "CA":
                rows.append(row)
    return rows


def sample_by_year(
    rows: list[dict],
    n: int,
    seed: int,
) -> dict[int, list[dict]]:
    """Stratified random sample of N grants per fiscal year.

    Returns dict mapping FY (int) -> sampled rows.
    Skips years in SKIP_YEARS. Warns if a year has fewer than N grants.
    """
    by_year: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        fy = int(row["FY"])
        by_year[fy].append(row)

    rng = random.Random(seed)
    sampled: dict[int, list[dict]] = {}

    for fy in sorted(by_year):
        if fy in SKIP_YEARS:
            print(f"  FY{fy}: SKIPPED (abstracts missing)")
            continue
        pool = by_year[fy]
        if len(pool) <= n:
            print(f"  FY{fy}: taking all {len(pool)} grants (fewer than {n})")
            sampled[fy] = list(pool)
        else:
            sampled[fy] = rng.sample(pool, n)
            print(f"  FY{fy}: sampled {n} from {len(pool)} NCI grants")

    return sampled


def join_abstracts(
    sampled: dict[int, list[dict]],
    abs_dir: Path,
) -> list[dict]:
    """Join abstracts from zip files and flatten to a single list."""
    output_rows = []

    for fy in sorted(sampled):
        print(f"  Loading abstracts for FY{fy}...")
        abstracts = load_abstracts_for_year(fy, abs_dir)
        found = 0
        for row in sampled[fy]:
            app_id = row["APPLICATION_ID"].strip()
            abstract = abstracts.get(app_id, "")
            has_abstract = bool(abstract)
            if has_abstract:
                found += 1
            output_rows.append({
                "FY": row["FY"],
                "APPLICATION_ID": app_id,
                "ADMINISTERING_IC": row.get("ADMINISTERING_IC", ""),
                "IC_NAME": row.get("IC_NAME", ""),
                "ACTIVITY": row.get("ACTIVITY", ""),
                "TOTAL_COST": row.get("TOTAL_COST", ""),
                "EXPLICIT_BIOMARKER": row.get("EXPLICIT_BIOMARKER", ""),
                "PROJECT_TITLE": row.get("PROJECT_TITLE", ""),
                "ABSTRACT_TEXT": abstract,
                "HAS_ABSTRACT": str(has_abstract),
            })
        print(f"    → {found}/{len(sampled[fy])} abstracts found")

    return output_rows


def write_sample(rows: list[dict], output_path: Path) -> None:
    """Write sampled rows to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Sample NCI biomarker grants by fiscal year"
    )
    parser.add_argument(
        "--unified",
        default=str(
            Path(__file__).resolve().parent.parent
            / "data"
            / "nih_biomarker_unified_2004-2024.csv"
        ),
        help="Path to unified dataset CSV",
    )
    parser.add_argument(
        "--abs-dir",
        default=str(Path.home() / "Downloads"),
        help="Directory containing RePORTER_PRJABS_C_FY*.zip files",
    )
    parser.add_argument(
        "--output",
        default=str(
            Path(__file__).resolve().parent.parent
            / "data"
            / "oncology_sample_100per_year.csv"
        ),
        help="Output CSV path",
    )
    parser.add_argument("--n", type=int, default=100, help="Grants per year")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"Loading NCI grants from {args.unified}...")
    nci_grants = load_nci_grants(Path(args.unified))
    print(f"  Found {len(nci_grants)} NCI grants total\n")

    print(f"Sampling {args.n} per year (seed={args.seed})...")
    sampled = sample_by_year(nci_grants, args.n, args.seed)
    total_sampled = sum(len(v) for v in sampled.values())
    print(f"\n  Total sampled: {total_sampled} grants across {len(sampled)} years\n")

    print("Joining abstracts...")
    output_rows = join_abstracts(sampled, Path(args.abs_dir))

    with_abs = sum(1 for r in output_rows if r["HAS_ABSTRACT"] == "True")
    without_abs = len(output_rows) - with_abs
    print(f"\n  With abstracts: {with_abs}")
    print(f"  Without abstracts: {without_abs}")

    print(f"\nWriting {len(output_rows)} rows to {args.output}...")
    write_sample(output_rows, Path(args.output))
    print("Done.")


if __name__ == "__main__":
    main()
