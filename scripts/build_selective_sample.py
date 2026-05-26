"""Build a small selective sample for rubric-iteration grading runs.

Combines three blocks into a single CSV consumable by ``inspect_task.py``:

  Block A — Gold-labeled rows from ``data/grader_calibration_examples.csv``
            (rows with non-empty ``GOLD_DIM1``). Tests whether models agree
            with researcher-confirmed labels for ``disease_non_biomarker``
            and ``not_applicable``.

  Block B — Stratified-random CA grants from ``data/nci_sample_v31_seed42.csv``.
            Stratified across activity-code buckets so we see new-code
            behaviour on a representative mix of mechanisms. Uses a sub-seed
            distinct from the production seed.

  Block C — (optional) Disagreement-prone grants extracted from prior NCI
            ``.eval`` files. Pairs Gemini vs GPT outputs on APPLICATION_ID;
            keeps rows where dim1 differs on the ``not_applicable`` /
            ``disease_non_biomarker`` / biomarker-code axis. Skipped when
            ``.eval`` files are not present locally.

Output: ``data/selective_v1_nci.csv``. Columns are schema-compatible with
``inspect_task.record_to_sample``. A ``SOURCE`` column tracks block origin
(``gold`` / ``random`` / ``disagreement``) for downstream analysis but is
ignored by ``record_to_sample``.

Usage:
    python3 scripts/build_selective_sample.py \\
        --nci-sample data/nci_sample_v31_seed42.csv \\
        --calibration data/grader_calibration_examples.csv \\
        --out data/selective_v1_nci.csv \\
        --n-random 50 --seed 4242

To also include Block C (requires prior .eval files):
    python3 scripts/build_selective_sample.py ... \\
        --include-disagreements \\
        --gemini-eval-dir logs/nci-v31-gemini-flash-lite/ \\
        --gpt-eval-dir logs/nci-v31-gpt-oss-120b/ \\
        --n-disagreement 30
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUT_COLUMNS = [
    "SOURCE",
    "APPLICATION_ID",
    "FY",
    "ADMINISTERING_IC",
    "IC_NAME",
    "ACTIVITY",
    "TOTAL_COST",
    "EXPLICIT_BIOMARKER",
    "PROJECT_TITLE",
    "ABSTRACT_TEXT",
    "HAS_ABSTRACT",
    "MATCHED_TERMS",
    "GOLD_DIM1",
    "GOLD_DIM2",
    "GOLD_DIM3",
]


def normalize_row(row: dict, source: str) -> dict:
    """Map either calibration or NCI-sample column names to the output schema."""
    abstract = row.get("ABSTRACT_TEXT") or row.get("ABSTRACT") or ""
    fy = row.get("FY") or row.get("YEAR") or ""
    return {
        "SOURCE": source,
        "APPLICATION_ID": row.get("APPLICATION_ID", ""),
        "FY": fy,
        "ADMINISTERING_IC": row.get("ADMINISTERING_IC", ""),
        "IC_NAME": row.get("IC_NAME", ""),
        "ACTIVITY": row.get("ACTIVITY", ""),
        "TOTAL_COST": row.get("TOTAL_COST", ""),
        "EXPLICIT_BIOMARKER": row.get("EXPLICIT_BIOMARKER", ""),
        "PROJECT_TITLE": row.get("PROJECT_TITLE", ""),
        "ABSTRACT_TEXT": abstract,
        "HAS_ABSTRACT": row.get(
            "HAS_ABSTRACT", "True" if abstract.strip() else "False"
        ),
        "MATCHED_TERMS": row.get("MATCHED_TERMS", ""),
        "GOLD_DIM1": row.get("GOLD_DIM1", ""),
        "GOLD_DIM2": row.get("GOLD_DIM2", ""),
        "GOLD_DIM3": row.get("GOLD_DIM3", ""),
    }


def load_gold_rows(calibration_csv: Path) -> list[dict]:
    """Read calibration CSV, return rows with non-empty GOLD_DIM1."""
    with calibration_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            normalize_row(row, source="gold")
            for row in reader
            if (row.get("GOLD_DIM1") or "").strip()
        ]


def load_nci_rows(nci_csv: Path) -> list[dict]:
    """Read NCI sample, drop rows without an abstract."""
    with nci_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[dict] = []
        for row in reader:
            abstract = (row.get("ABSTRACT_TEXT") or row.get("ABSTRACT") or "").strip()
            if not abstract:
                continue
            rows.append(row)
    return rows


def stratified_sample(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Stratify by activity-code bucket, then random-sample to total ``n``.

    Buckets are coarse so we get a mix even with N=50:
        R01 / R21 / R03 / K* / F* / U* / T* / P* / other
    """

    def bucket(act: str) -> str:
        act = (act or "").upper().strip()
        if act in {"R01", "R21", "R03"}:
            return act
        if act.startswith("K"):
            return "K*"
        if act.startswith("F"):
            return "F*"
        if act.startswith("U"):
            return "U*"
        if act.startswith("T"):
            return "T*"
        if act.startswith("P"):
            return "P*"
        return "other"

    by_bucket: dict[str, list[dict]] = {}
    for r in rows:
        by_bucket.setdefault(bucket(r.get("ACTIVITY", "")), []).append(r)

    buckets = sorted(by_bucket.keys())
    total = sum(len(v) for v in by_bucket.values())
    if total == 0:
        return []

    # Proportional allocation per bucket, floored at 1 where the bucket exists.
    raw_alloc = {b: max(1, round(n * len(by_bucket[b]) / total)) for b in buckets}
    # Trim/grow to exactly n.
    while sum(raw_alloc.values()) > n:
        biggest = max(raw_alloc, key=lambda b: raw_alloc[b])
        if raw_alloc[biggest] <= 1:
            break
        raw_alloc[biggest] -= 1
    while sum(raw_alloc.values()) < n:
        smallest = min(raw_alloc, key=lambda b: raw_alloc[b])
        raw_alloc[smallest] += 1

    sampled: list[dict] = []
    for b in buckets:
        take = min(raw_alloc[b], len(by_bucket[b]))
        sampled.extend(rng.sample(by_bucket[b], take))
    return [normalize_row(r, source="random") for r in sampled]


# ---------------------------------------------------------------------------
# Optional Block C: disagreement extraction from prior .eval logs
# ---------------------------------------------------------------------------


def _dim1_per_app(eval_dir: Path) -> dict[str, str]:
    """Map APPLICATION_ID -> dim1_primary for the most recent .eval in dir."""
    try:
        from scripts.analyze_eval_results import extract_scores, load_eval_log
    except ImportError:
        return {}

    eval_files = sorted(eval_dir.glob("*.eval"))
    if not eval_files:
        return {}
    log = load_eval_log(eval_files[-1])
    out: dict[str, str] = {}
    for s in log["samples"]:
        row = extract_scores(s)
        if row and row.get("sample_id") and row.get("dim1_primary"):
            out[str(row["sample_id"])] = row["dim1_primary"]
    return out


def load_disagreement_rows(
    nci_rows: list[dict],
    gemini_dir: Path,
    gpt_dir: Path,
    n: int,
    rng: random.Random,
) -> list[dict]:
    """Find rows where the two models disagreed on the not_applicable axis."""
    gem = _dim1_per_app(gemini_dir)
    gpt = _dim1_per_app(gpt_dir)
    if not gem or not gpt:
        print(
            f"  [disagreement] skipped — gemini={len(gem)} gpt={len(gpt)} samples found",
            file=sys.stderr,
        )
        return []

    reject_codes = {"not_applicable", "disease_non_biomarker"}
    candidates: list[dict] = []
    for r in nci_rows:
        app_id = str(r.get("APPLICATION_ID", ""))
        g, p = gem.get(app_id), gpt.get(app_id)
        if not g or not p or g == p:
            continue
        # Keep cases where exactly one model rejected (biomarker vs not_applicable).
        if (g in reject_codes) != (p in reject_codes):
            candidates.append(r)

    print(f"  [disagreement] {len(candidates)} candidate rows", file=sys.stderr)
    if not candidates:
        return []
    take = min(n, len(candidates))
    return [
        normalize_row(r, source="disagreement") for r in rng.sample(candidates, take)
    ]


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--nci-sample", type=Path, default=Path("data/nci_sample_v31_seed42.csv")
    )
    p.add_argument(
        "--calibration", type=Path, default=Path("data/grader_calibration_examples.csv")
    )
    p.add_argument("--out", type=Path, default=Path("data/selective_v1_nci.csv"))
    p.add_argument("--n-random", type=int, default=50)
    p.add_argument(
        "--seed",
        type=int,
        default=4242,
        help="Sub-seed for random block (distinct from production seed 42)",
    )
    p.add_argument("--include-disagreements", action="store_true")
    p.add_argument(
        "--gemini-eval-dir", type=Path, default=Path("logs/nci-v31-gemini-flash-lite/")
    )
    p.add_argument(
        "--gpt-eval-dir", type=Path, default=Path("logs/nci-v31-gpt-oss-120b/")
    )
    p.add_argument("--n-disagreement", type=int, default=30)
    args = p.parse_args()

    if not args.nci_sample.exists():
        print(
            f"ERROR: {args.nci_sample} not found. Run bash scripts/download-dataset.sh first.",
            file=sys.stderr,
        )
        return 1
    if not args.calibration.exists():
        print(f"ERROR: {args.calibration} not found.", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)

    print(f"Loading gold rows from {args.calibration}", file=sys.stderr)
    gold = load_gold_rows(args.calibration)
    print(f"  {len(gold)} gold-labeled rows", file=sys.stderr)

    print(f"Loading NCI sample from {args.nci_sample}", file=sys.stderr)
    nci = load_nci_rows(args.nci_sample)
    print(f"  {len(nci)} NCI rows with abstracts", file=sys.stderr)

    gold_ids = {r["APPLICATION_ID"] for r in gold}
    nci_for_sampling = [
        r for r in nci if str(r.get("APPLICATION_ID", "")) not in gold_ids
    ]

    random_rows = stratified_sample(nci_for_sampling, args.n_random, rng)
    print(f"  {len(random_rows)} random rows", file=sys.stderr)

    disagreement_rows: list[dict] = []
    if args.include_disagreements:
        print("Loading disagreement rows from prior .eval files", file=sys.stderr)
        sampled_ids = {r["APPLICATION_ID"] for r in random_rows} | gold_ids
        nci_for_disagree = [
            r for r in nci if str(r.get("APPLICATION_ID", "")) not in sampled_ids
        ]
        disagreement_rows = load_disagreement_rows(
            nci_for_disagree,
            args.gemini_eval_dir,
            args.gpt_eval_dir,
            args.n_disagreement,
            rng,
        )
        print(f"  {len(disagreement_rows)} disagreement rows", file=sys.stderr)

    all_rows = gold + random_rows + disagreement_rows
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows -> {args.out}", file=sys.stderr)
    src_counts: dict[str, int] = {}
    for r in all_rows:
        src_counts[r["SOURCE"]] = src_counts.get(r["SOURCE"], 0) + 1
    for src, n in sorted(src_counts.items()):
        print(f"  {src:<14} {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
