#!/usr/bin/env python3
"""
Analyze PROJECT_TERMS distribution to find biomarker-concept terms missing from keyword filter.

Compares term frequencies between the full NIH ExPORTER corpus and our biomarker-filtered
subset, identifying terms that appear independently (without our current keywords) in grants
we're not capturing.

Usage:
    python3 scripts/analyze_keyword_distribution.py \
        --raw-dir ~/Downloads \
        --filtered-dir data/filtered/keywords \
        --output data/keyword_distribution_analysis.csv
"""

import argparse
import csv
import io
import logging
import sys
import zipfile
from collections import Counter
from pathlib import Path

# Import current keyword lists
sys.path.insert(0, str(Path(__file__).parent))
from filter_biomarker_projects import EXPANDED_BIOMARKER_TERMS, contains_biomarker_terms

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_project_terms(terms_str: str) -> list[str]:
    """Split semicolon-delimited PROJECT_TERMS into normalized individual terms."""
    if not terms_str or not terms_str.strip():
        return []
    return [t.strip().lower() for t in terms_str.split(";") if t.strip()]


def load_biomarker_ids(filtered_dir: Path) -> set[tuple[str, str]]:
    """Load (APPLICATION_ID, FY) pairs from filtered keyword CSVs."""
    ids = set()
    for csv_path in sorted(filtered_dir.glob("biomarker_FY*.csv")):
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                app_id = row.get("APPLICATION_ID", "").strip()
                fy = row.get("FY", "").strip()
                if app_id and fy:
                    ids.add((app_id, fy))
    logger.info(f"Loaded {len(ids):,} biomarker grant records from {filtered_dir}")
    return ids


def grant_has_current_keywords(project_terms: str, project_title: str) -> bool:
    """Check if a grant already matches our current expanded keyword set."""
    combined = f"{project_title} {project_terms}"
    return contains_biomarker_terms(combined, EXPANDED_BIOMARKER_TERMS)


def process_year_zip(
    zip_path: Path,
    biomarker_ids: set[tuple[str, str]],
    fy: str,
) -> tuple[Counter, Counter, Counter, int, int]:
    """Process one fiscal year's ExPORTER zip file.

    Returns:
        all_term_counts: term frequency across all grants
        biomarker_term_counts: term frequency in biomarker-filtered grants
        independent_term_counts: term frequency in grants WITHOUT current keywords
        total_grants: number of grants processed
        terms_empty_count: grants with empty PROJECT_TERMS
    """
    all_counts: Counter = Counter()
    biomarker_counts: Counter = Counter()
    independent_counts: Counter = Counter()
    total = 0
    empty = 0

    with zipfile.ZipFile(zip_path) as z:
        csv_names = [n for n in z.namelist() if n.endswith(".csv")]
        if not csv_names:
            logger.warning(f"No CSV found in {zip_path}")
            return all_counts, biomarker_counts, independent_counts, 0, 0

        with z.open(csv_names[0]) as f:
            reader = csv.DictReader(
                io.TextIOWrapper(f, encoding="utf-8", errors="ignore")
            )
            for row in reader:
                total += 1
                project_terms_raw = row.get("PROJECT_TERMS", "")
                project_title = row.get("PROJECT_TITLE", "")
                app_id = row.get("APPLICATION_ID", "").strip()

                terms = parse_project_terms(project_terms_raw)
                if not terms:
                    empty += 1
                    continue

                # Deduplicate terms within this grant
                unique_terms = set(terms)

                # Update all-grants counts
                all_counts.update(unique_terms)

                # Check if this grant is in our biomarker-filtered set
                is_biomarker = (app_id, fy) in biomarker_ids

                if is_biomarker:
                    biomarker_counts.update(unique_terms)

                # Check if this grant has current keywords
                has_keywords = grant_has_current_keywords(
                    project_terms_raw, project_title
                )

                if not has_keywords:
                    # Grant does NOT match any current keyword — these terms appear independently
                    independent_counts.update(unique_terms)

    return all_counts, biomarker_counts, independent_counts, total, empty


def process_year_csv(
    csv_path: Path,
    biomarker_ids: set[tuple[str, str]],
    fy: str,
) -> tuple[Counter, Counter, Counter, int, int]:
    """Process a bare CSV (not zipped) for one fiscal year."""
    all_counts: Counter = Counter()
    biomarker_counts: Counter = Counter()
    independent_counts: Counter = Counter()
    total = 0
    empty = 0

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            project_terms_raw = row.get("PROJECT_TERMS", "")
            project_title = row.get("PROJECT_TITLE", "")
            app_id = row.get("APPLICATION_ID", "").strip()

            terms = parse_project_terms(project_terms_raw)
            if not terms:
                empty += 1
                continue

            unique_terms = set(terms)
            all_counts.update(unique_terms)

            is_biomarker = (app_id, fy) in biomarker_ids
            if is_biomarker:
                biomarker_counts.update(unique_terms)

            has_keywords = grant_has_current_keywords(project_terms_raw, project_title)
            if not has_keywords:
                independent_counts.update(unique_terms)

    return all_counts, biomarker_counts, independent_counts, total, empty


def main():
    parser = argparse.ArgumentParser(
        description="Analyze PROJECT_TERMS distribution for missing biomarker keywords"
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path.home() / "Downloads",
        help="Directory with RePORTER_PRJ_C_FY*.zip files",
    )
    parser.add_argument(
        "--filtered-dir",
        type=Path,
        default=Path("data/filtered/keywords"),
        help="Directory with biomarker_FY*.csv filtered files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/keyword_distribution_analysis.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--min-freq",
        type=int,
        default=100,
        help="Minimum total frequency to include a term (default: 100)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Number of top candidate terms to display (default: 100)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2004,
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2024,
    )
    args = parser.parse_args()

    # Load biomarker-filtered grant IDs
    biomarker_ids = load_biomarker_ids(args.filtered_dir)

    # Aggregate counts across all years
    total_all: Counter = Counter()
    total_biomarker: Counter = Counter()
    total_independent: Counter = Counter()
    total_grants = 0
    total_empty = 0

    for year in range(args.start_year, args.end_year + 1):
        fy = str(year)

        # Try zip first, then bare CSV
        zip_path = args.raw_dir / f"RePORTER_PRJ_C_FY{year}.zip"
        csv_path = args.raw_dir / f"RePORTER_PRJ_C_FY{year}.csv"

        if zip_path.exists():
            logger.info(f"Processing FY{year} (zip)...")
            all_c, bio_c, ind_c, n, emp = process_year_zip(zip_path, biomarker_ids, fy)
        elif csv_path.exists():
            logger.info(f"Processing FY{year} (csv)...")
            all_c, bio_c, ind_c, n, emp = process_year_csv(csv_path, biomarker_ids, fy)
        else:
            logger.warning(f"No data file found for FY{year}, skipping")
            continue

        total_all += all_c
        total_biomarker += bio_c
        total_independent += ind_c
        total_grants += n
        total_empty += emp

        terms_pct = (1 - emp / n) * 100 if n > 0 else 0
        logger.info(
            f"  FY{year}: {n:,} grants, {terms_pct:.0f}% have PROJECT_TERMS, "
            f"{bio_c.total():,} biomarker term occurrences"
        )

    logger.info(
        f"\nTotal: {total_grants:,} grants processed, {total_empty:,} with empty PROJECT_TERMS"
    )
    logger.info(f"Unique terms found: {len(total_all):,}")

    # Build results table
    n_all = total_grants - total_empty  # grants with non-empty PROJECT_TERMS
    n_biomarker = len(biomarker_ids)  # number of biomarker grants
    base_rate = n_biomarker / n_all if n_all > 0 else 0

    logger.info(f"Biomarker base rate: {n_biomarker:,} / {n_all:,} = {base_rate:.4f}")

    results = []
    for term, all_freq in total_all.items():
        if all_freq < args.min_freq:
            continue

        bio_freq = total_biomarker.get(term, 0)
        ind_freq = total_independent.get(term, 0)

        # Co-occurrence rate: fraction of this term's appearances that are in grants
        # already matched by our current keywords
        # co_occurrence_rate = 1 means this term always appears WITH our keywords (redundant)
        # co_occurrence_rate = 0 means this term never appears with our keywords (novel)
        co_occurrence_rate = 1 - (ind_freq / all_freq) if all_freq > 0 else 0

        # Enrichment ratio: how overrepresented is this term in biomarker grants?
        # enrichment = (bio_freq/n_biomarker) / (all_freq/n_all)
        # >1 means the term is more common in biomarker grants than NIH overall
        term_rate_bio = bio_freq / n_biomarker if n_biomarker > 0 else 0
        term_rate_all = all_freq / n_all if n_all > 0 else 0
        enrichment = term_rate_bio / term_rate_all if term_rate_all > 0 else 0

        results.append(
            {
                "term": term,
                "total_freq": all_freq,
                "biomarker_freq": bio_freq,
                "independent_freq": ind_freq,
                "co_occurrence_rate": round(co_occurrence_rate, 4),
                "enrichment_ratio": round(enrichment, 4),
            }
        )

    # Sort by enrichment ratio (most overrepresented in biomarker grants first)
    results.sort(key=lambda r: r["enrichment_ratio"], reverse=True)

    # Write full results CSV
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "term",
                "total_freq",
                "biomarker_freq",
                "independent_freq",
                "co_occurrence_rate",
                "enrichment_ratio",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"\nWrote {len(results):,} terms to {args.output}")

    # Display top candidates:
    # - High enrichment (>1.5 = 50% more common in biomarker grants)
    # - Low co-occurrence (<0.8 = appears independently, not already captured)
    # - Exclude terms that are just generic NIH vocabulary (enrichment ~1.0)
    print("\n" + "=" * 100)
    print("TOP CANDIDATE TERMS: enriched in biomarker grants AND appear independently")
    print("(enrichment > 1.5, co_occurrence < 0.8, sorted by enrichment_ratio)")
    print("=" * 100)
    print(
        f"{'term':<40} {'total':>8} {'biomarker':>10} {'independent':>12} "
        f"{'co_occur':>9} {'enrich':>8}"
    )
    print("-" * 100)

    shown = 0
    for r in results:
        if r["co_occurrence_rate"] >= 0.8:
            continue
        if r["enrichment_ratio"] <= 1.5:
            continue
        if shown >= args.top_n:
            break
        print(
            f"{r['term']:<40} {r['total_freq']:>8,} {r['biomarker_freq']:>10,} "
            f"{r['independent_freq']:>12,} {r['co_occurrence_rate']:>9.2%} "
            f"{r['enrichment_ratio']:>8.2f}"
        )
        shown += 1

    # Also show high-enrichment terms WITH high co-occurrence (already captured but interesting)
    print("\n" + "=" * 100)
    print(
        "HIGH CO-OCCURRENCE TERMS (>0.8, enrichment > 2.0) — REDUNDANT, already captured"
    )
    print("=" * 100)
    print(
        f"{'term':<40} {'total':>8} {'biomarker':>10} {'independent':>12} "
        f"{'co_occur':>9} {'enrich':>8}"
    )
    print("-" * 100)

    redundant = [
        r
        for r in results
        if r["co_occurrence_rate"] >= 0.8
        and r["enrichment_ratio"] > 2.0
        and r["biomarker_freq"] > 500
    ]
    redundant.sort(key=lambda r: r["enrichment_ratio"], reverse=True)
    for r in redundant[:30]:
        print(
            f"{r['term']:<40} {r['total_freq']:>8,} {r['biomarker_freq']:>10,} "
            f"{r['independent_freq']:>12,} {r['co_occurrence_rate']:>9.2%} "
            f"{r['enrichment_ratio']:>8.2f}"
        )


if __name__ == "__main__":
    main()
