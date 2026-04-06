"""
General-purpose stratified grant sampler for multi-IC pilot studies.

Tiered sampling rates: CA gets 5%, ICs with >=20K grants get 7%, smaller ICs get 10%.
Stratified by fiscal year within each IC, with a configurable floor per stratum.

Usage:
    python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv \
        --abs-dir ~/Downloads --seed 42

    python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv \
        --abs-dir ~/Downloads --seed 42 --output data/pilot_sample_12IC_5pct_seed42.csv

    python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv \
        --abs-dir ~/Downloads --seed 42 --dry-run
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

DEFAULT_ICS = ["CA", "HL", "AG", "AI", "NS", "MH", "DK", "HD", "GM", "DA", "EB", "AR"]

OUTPUT_COLUMNS = [
    "FY",
    "APPLICATION_ID",
    "ADMINISTERING_IC",
    "IC_NAME",
    "ACTIVITY",
    "TOTAL_COST",
    "EXPLICIT_BIOMARKER",
    "MATCH_SOURCE",
    "PROJECT_TITLE",
    "ABSTRACT_TEXT",
    "HAS_ABSTRACT",
]


def assign_rate(ic: str, pool_size: int) -> float:
    """Tiered sampling rate.

    CA: 5%, >=20K grants: 7%, <20K: 10%.
    """
    if ic == "CA":
        return 0.05
    if pool_size >= 20_000:
        return 0.07
    return 0.10


def stratified_sample(
    rows: list[dict],
    rate: float,
    min_per_stratum: int,
    seed: int,
) -> list[dict]:
    """Stratified random sample by FY. Apply rate with floor min_per_stratum.

    If pool < min_per_stratum, take all.
    """
    by_fy: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_fy[row["FY"]].append(row)

    rng = random.Random(seed)
    sampled: list[dict] = []

    for fy in sorted(by_fy):
        pool = by_fy[fy]
        n = max(min_per_stratum, round(len(pool) * rate))
        if len(pool) <= n:
            sampled.extend(pool)
        else:
            sampled.extend(rng.sample(pool, n))

    return sampled


def load_grants(csv_path: Path, ics: list[str]) -> list[dict]:
    """Load unified dataset and filter to specified ICs."""
    ic_set = set(ics)
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("ADMINISTERING_IC", "").strip() in ic_set:
                rows.append(row)
    return rows


def join_abstracts(
    sampled: list[dict],
    abs_dir: Path,
    skip_years: set[int],
) -> list[dict]:
    """Join abstracts from zip files for sampled grants."""
    # Group by FY for efficient abstract loading
    by_fy: dict[int, list[dict]] = defaultdict(list)
    for row in sampled:
        by_fy[int(row["FY"])].append(row)

    output_rows = []
    for fy in sorted(by_fy):
        if fy in skip_years:
            print(f"  FY{fy}: SKIPPED (abstracts missing)")
            # Still include rows, just without abstracts
            for row in by_fy[fy]:
                output_rows.append(_make_output_row(row, abstract=""))
            continue

        print(f"  Loading abstracts for FY{fy}...")
        abstracts = load_abstracts_for_year(fy, abs_dir)
        found = 0
        for row in by_fy[fy]:
            app_id = row["APPLICATION_ID"].strip()
            abstract = abstracts.get(app_id, "")
            if abstract:
                found += 1
            output_rows.append(_make_output_row(row, abstract))
        print(f"    -> {found}/{len(by_fy[fy])} abstracts found")

    return output_rows


def _make_output_row(row: dict, abstract: str) -> dict:
    """Build an output row dict from a grant row and its abstract."""
    return {
        "FY": row["FY"],
        "APPLICATION_ID": row["APPLICATION_ID"].strip(),
        "ADMINISTERING_IC": row.get("ADMINISTERING_IC", ""),
        "IC_NAME": row.get("IC_NAME", ""),
        "ACTIVITY": row.get("ACTIVITY", ""),
        "TOTAL_COST": row.get("TOTAL_COST", ""),
        "EXPLICIT_BIOMARKER": row.get("EXPLICIT_BIOMARKER", ""),
        "MATCH_SOURCE": row.get("MATCH_SOURCE", ""),
        "PROJECT_TITLE": row.get("PROJECT_TITLE", ""),
        "ABSTRACT_TEXT": abstract,
        "HAS_ABSTRACT": str(bool(abstract)),
    }


def write_sample(rows: list[dict], output_path: Path) -> None:
    """Write sampled rows to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(
    ic_stats: list[dict],
    all_sampled: list[dict],
    skip_years: set[int],
) -> None:
    """Print sampling summary."""
    print("\n--- Sampling Summary ---")
    print(f"{'IC':<6} {'Pool':>8} {'Rate':>8} {'Sampled':>8}")
    print("-" * 34)
    for stat in ic_stats:
        print(
            f"{stat['ic']:<6} {stat['pool']:>8,} {stat['rate']:>7.0%} {stat['sampled']:>8,}"
        )

    total_sampled = len(all_sampled)
    print(f"\nTotal sampled: {total_sampled:,}")

    # Per-year summary
    by_year: dict[str, int] = defaultdict(int)
    for row in all_sampled:
        by_year[row["FY"]] += 1
    print("\nPer year:")
    for fy in sorted(by_year):
        note = " (abstracts missing)" if int(fy) in skip_years else ""
        print(f"  FY{fy}: {by_year[fy]:,}{note}")

    # Abstract stats (only available after join)
    with_abs = sum(1 for r in all_sampled if r.get("HAS_ABSTRACT") == "True")
    without_abs = sum(1 for r in all_sampled if r.get("HAS_ABSTRACT") == "False")
    if with_abs or without_abs:
        print(f"\nWith abstracts: {with_abs:,}")
        print(f"Without abstracts: {without_abs:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Stratified grant sampler for multi-IC pilot studies"
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
        "--ics",
        nargs="+",
        default=DEFAULT_ICS,
        help=f"IC codes to sample (default: {' '.join(DEFAULT_ICS)})",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Override rate for all ICs (omit for tiered defaults)",
    )
    parser.add_argument(
        "--min-per-stratum",
        type=int,
        default=50,
        help="Floor per FY stratum (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: auto-generated)",
    )
    parser.add_argument(
        "--skip-years",
        nargs="*",
        type=int,
        default=[],
        help="Years to skip (default: none)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing",
    )
    args = parser.parse_args()

    skip_years = set(args.skip_years)

    # Auto-generate output path if not specified
    if args.output is None:
        n_ics = len(args.ics)
        rate_label = f"{int(args.rate * 100)}pct" if args.rate else "tiered"
        output_path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / f"pilot_sample_{n_ics}IC_{rate_label}_seed{args.seed}.csv"
        )
    else:
        output_path = Path(args.output)

    print(f"Loading grants from {args.unified}...")
    all_grants = load_grants(Path(args.unified), args.ics)
    print(f"  Found {len(all_grants):,} grants across {len(args.ics)} ICs\n")

    # Group by IC
    by_ic: dict[str, list[dict]] = defaultdict(list)
    for row in all_grants:
        by_ic[row["ADMINISTERING_IC"].strip()].append(row)

    # Sample each IC
    all_sampled: list[dict] = []
    ic_stats: list[dict] = []

    for ic in sorted(args.ics):
        ic_grants = by_ic.get(ic, [])
        pool_size = len(ic_grants)
        rate = args.rate if args.rate is not None else assign_rate(ic, pool_size)

        if pool_size == 0:
            print(f"  {ic}: no grants found, skipping")
            ic_stats.append({"ic": ic, "pool": 0, "rate": rate, "sampled": 0})
            continue

        ic_sampled = stratified_sample(
            ic_grants,
            rate=rate,
            min_per_stratum=args.min_per_stratum,
            seed=args.seed,
        )
        all_sampled.extend(ic_sampled)
        ic_stats.append(
            {
                "ic": ic,
                "pool": pool_size,
                "rate": rate,
                "sampled": len(ic_sampled),
            }
        )

    if args.dry_run:
        print_summary(ic_stats, all_sampled, skip_years)
        print(f"\n[dry-run] Would write to: {output_path}")
        return

    # Join abstracts
    print("\nJoining abstracts...")
    output_rows = join_abstracts(all_sampled, Path(args.abs_dir), skip_years)

    print_summary(ic_stats, output_rows, skip_years)

    print(f"\nWriting {len(output_rows):,} rows to {output_path}...")
    write_sample(output_rows, output_path)
    print("Done.")


if __name__ == "__main__":
    main()
