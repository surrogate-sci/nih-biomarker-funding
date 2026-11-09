"""Fixed-count-per-year sample of biomarker-screened grants for one IC.

Draws a fixed number of grants per fiscal year from the unified dataset for a
single administering IC, applying the same P30 filter as ``sample_grants.py``
(P30 excluded unless NIH_SPENDING_CATS contains "clinical"). Only grants whose
abstract is found in the RePORTER zips are eligible, so each year yields the
requested count when enough abstracts exist.

Usage:
    python3 scripts/sample_ic_by_year.py --ic ES \\
        --per-year 2004-2013:10 --per-year 2014-2023:20 \\
        --abs-dir ~/Downloads --seed 42 \\
        --out data/niehs_sample_byyear_seed42.csv
"""

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.abstract_loader import load_abstracts_for_year  # noqa: E402
from scripts.sample_grants import _make_output_row, load_grants, write_sample  # noqa: E402


def parse_per_year(specs: list[str]) -> dict[int, int]:
    """Parse ``START-END:N`` specs into {fy: n}."""
    out: dict[int, int] = {}
    for spec in specs:
        years, n = spec.split(":")
        start, end = (int(y) for y in years.split("-"))
        for fy in range(start, end + 1):
            out[fy] = int(n)
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--unified", type=Path, default=Path("data/nih_biomarker_unified_2004-2024.csv")
    )
    p.add_argument("--ic", required=True)
    p.add_argument(
        "--per-year", action="append", required=True, help="START-END:N, repeatable"
    )
    p.add_argument("--abs-dir", type=Path, default=Path.home() / "Downloads")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    csv.field_size_limit(10**9)
    targets = parse_per_year(args.per_year)
    rows = load_grants(args.unified, [args.ic])
    by_fy: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_fy[int(r["FY"])].append(r)

    rng = random.Random(args.seed)
    out = []
    for fy in sorted(targets):
        pool = sorted(by_fy.get(fy, []), key=lambda r: r["APPLICATION_ID"])
        rng.shuffle(pool)
        abstracts = load_abstracts_for_year(fy, args.abs_dir)
        picked = []
        for r in pool:
            a = abstracts.get(r["APPLICATION_ID"].strip(), "")
            if a:
                picked.append(_make_output_row(r, a))
            if len(picked) == targets[fy]:
                break
        flag = "" if len(picked) == targets[fy] else "  (SHORT)"
        print(f"  FY{fy}: pool={len(pool)} picked={len(picked)}/{targets[fy]}{flag}")
        out.extend(picked)

    write_sample(out, args.out)
    print(f"Wrote {len(out)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
