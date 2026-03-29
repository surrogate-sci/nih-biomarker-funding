#!/usr/bin/env python3
"""Analyze inter-rater agreement between LLM graders on oncology grants.

Usage:
    python3 scripts/analyze_agreement.py
    python3 scripts/analyze_agreement.py --data-dir /path/to/grades
"""

import argparse
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"

DEFAULT_FILES = {
    "gemini": "oncology_grades_gemini-2.5-flash-lite.jsonl",
    "gpt4o-mini": "oncology_grades_gpt-4o-mini.jsonl",
    "gpt41-mini": "oncology_grades_gpt-4.1-mini.jsonl",
}

MODEL_LABELS = {
    "gemini": "Gemini 2.5 Flash Lite",
    "gpt4o-mini": "GPT-4o-mini",
    "gpt41-mini": "GPT-4.1-mini",
}


def load_grades(path):
    """Load JSONL, skip error records. Returns dict keyed by application_id."""
    grades = {}
    errors = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "error" in rec and not isinstance(rec.get("classification"), dict):
                errors += 1
                continue
            c = rec.get("classification")
            if not isinstance(c, dict):
                errors += 1
                continue
            grades[rec["application_id"]] = {
                "dim1": c["biomarker_use"]["primary"],
                "dim1_sec": c["biomarker_use"].get("secondary"),
                "dim2": c["research_design"]["primary"],
                "dim2_sec": c["research_design"].get("secondary"),
                "dim3": c["evidence_strength"]["code"],
                "title": rec.get("title", ""),
            }
    return grades, errors


def compute_agreement(grades_a, grades_b, label_a, label_b, common_ids):
    """Compute agreement stats for a pair of graders on common IDs."""
    n = len(common_ids)
    if n == 0:
        return None

    dim1_agree = 0
    dim2_agree = 0
    dim3_agree = 0
    dim1_disagree = Counter()
    dim2_disagree = Counter()
    dim3_disagree = Counter()

    for aid in common_ids:
        a, b = grades_a[aid], grades_b[aid]
        if a["dim1"] == b["dim1"]:
            dim1_agree += 1
        else:
            dim1_disagree[(a["dim1"], b["dim1"])] += 1
        if a["dim2"] == b["dim2"]:
            dim2_agree += 1
        else:
            dim2_disagree[(a["dim2"], b["dim2"])] += 1
        if a["dim3"] == b["dim3"]:
            dim3_agree += 1
        else:
            dim3_disagree[(a["dim3"], b["dim3"])] += 1

    return {
        "n": n,
        "dim1_rate": dim1_agree / n,
        "dim2_rate": dim2_agree / n,
        "dim3_rate": dim3_agree / n,
        "dim1_disagree": dim1_disagree,
        "dim2_disagree": dim2_disagree,
        "dim3_disagree": dim3_disagree,
    }


def compute_triple_agreement(all_grades, common_ids):
    """Compute agreement where all 3 models agree."""
    n = len(common_ids)
    if n == 0:
        return None

    keys = list(all_grades.keys())
    dim1_all = 0
    dim2_all = 0
    dim3_all = 0

    for aid in common_ids:
        vals = [all_grades[k][aid] for k in keys]
        if len(set(v["dim1"] for v in vals)) == 1:
            dim1_all += 1
        if len(set(v["dim2"] for v in vals)) == 1:
            dim2_all += 1
        if len(set(v["dim3"] for v in vals)) == 1:
            dim3_all += 1

    return {
        "n": n,
        "dim1_rate": dim1_all / n,
        "dim2_rate": dim2_all / n,
        "dim3_rate": dim3_all / n,
    }


def print_disagreements(disagree_counter, label_a, label_b, dim_name, top_n=5):
    """Print top disagreement patterns."""
    if not disagree_counter:
        print(f"    No disagreements on {dim_name}")
        return
    total = sum(disagree_counter.values())
    print(f"    Top {dim_name} disagreements ({total} total):")
    for (va, vb), count in disagree_counter.most_common(top_n):
        pct = count / total * 100
        print(f"      {label_a}: {va}  vs  {label_b}: {vb}  — {count} ({pct:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description="Analyze inter-rater agreement between LLM graders")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory containing grade JSONL files (default: data/)",
    )
    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    # Resolve file paths and check existence
    files = {key: data_dir / fname for key, fname in DEFAULT_FILES.items()}
    missing = [key for key, path in files.items() if not path.exists()]
    if len(missing) == len(files):
        print(f"ERROR: No grade files found in {data_dir}", file=sys.stderr)
        sys.exit(1)
    for key in missing:
        print(f"WARNING: {files[key]} not found, skipping {MODEL_LABELS[key]}", file=sys.stderr)

    # Load all available files
    all_grades = {}
    print("=" * 80)
    print("LLM GRADER AGREEMENT ANALYSIS — NIH Biomarker Oncology Grants")
    print("=" * 80)
    print()

    for key, path in files.items():
        if key in missing:
            continue
        grades, errors = load_grades(path)
        all_grades[key] = grades
        print(f"  {MODEL_LABELS[key]:30s}: {len(grades):5d} valid grades, {errors} errors")

    print()

    # Find overlaps dynamically
    model_keys = list(all_grades.keys())
    ids = {k: set(v.keys()) for k, v in all_grades.items()}

    # Pairwise overlaps
    pairwise_overlaps = {}
    for ka, kb in itertools.combinations(model_keys, 2):
        pairwise_overlaps[(ka, kb)] = ids[ka] & ids[kb]

    # N-way overlap (intersection of all loaded models)
    nway_overlap = set.intersection(*ids.values()) if ids else set()

    print("OVERLAP COUNTS")
    print("-" * 50)
    if len(model_keys) >= 2:
        if len(model_keys) >= 3:
            print(f"  All {len(model_keys)} models:{' ' * (21 - len(str(len(model_keys))))} {len(nway_overlap):5d}")
        for (ka, kb), common in pairwise_overlaps.items():
            la = MODEL_LABELS.get(ka, ka)
            lb = MODEL_LABELS.get(kb, kb)
            label = f"{la} + {lb}:"
            print(f"  {label:35s} {len(common):5d}")
    else:
        print(f"  Only one model loaded ({MODEL_LABELS.get(model_keys[0], model_keys[0])}), no overlaps to compute.")
    print()

    # Pairwise agreement
    if len(model_keys) >= 2:
        print("=" * 80)
        print("PAIRWISE AGREEMENT RATES")
        print("=" * 80)
        print()
        print(f"  {'Pair':42s}   {'N':>5s}   {'Dim1':>6s}   {'Dim2':>6s}   {'Dim3':>6s}")
        print(f"  {'-'*42}   {'-----':>5s}   {'------':>6s}   {'------':>6s}   {'------':>6s}")

        pair_results = {}
        for (ka, kb), common in pairwise_overlaps.items():
            la = MODEL_LABELS.get(ka, ka)
            lb = MODEL_LABELS.get(kb, kb)
            res = compute_agreement(
                all_grades[ka], all_grades[kb],
                la, lb,
                common,
            )
            pair_results[(ka, kb)] = res
            label = f"{la} vs {lb}"
            if res:
                print(
                    f"  {label:42s}   {res['n']:5d}   {res['dim1_rate']:5.1%}   {res['dim2_rate']:5.1%}   {res['dim3_rate']:5.1%}"
                )
            else:
                print(f"  {label:42s}   {'0':>5s}   {'N/A':>6s}   {'N/A':>6s}   {'N/A':>6s}")

        print()

    # N-way agreement (only if 3+ models)
    if len(model_keys) >= 3 and nway_overlap:
        print("=" * 80)
        print(f"{len(model_keys)}-WAY AGREEMENT (all models must agree)")
        print("=" * 80)
        tres = compute_triple_agreement(all_grades, nway_overlap)
        print(f"  N = {tres['n']}")
        print(f"  Dim1 (biomarker use):   {tres['dim1_rate']:5.1%}")
        print(f"  Dim2 (research design): {tres['dim2_rate']:5.1%}")
        print(f"  Dim3 (evidence str.):   {tres['dim3_rate']:5.1%}")
        print()

    # Disagreement details
    if len(model_keys) >= 2:
        print("=" * 80)
        print("DISAGREEMENT PATTERNS (top 5 per dimension per pair)")
        print("=" * 80)
        for (ka, kb), common in pairwise_overlaps.items():
            res = pair_results[(ka, kb)]
            if not res:
                continue
            la = MODEL_LABELS.get(ka, ka)
            lb = MODEL_LABELS.get(kb, kb)
            print(f"\n  --- {la} vs {lb} (N={res['n']}) ---")
            print_disagreements(res["dim1_disagree"], la, lb, "Dim1 (biomarker use)")
            print_disagreements(res["dim2_disagree"], la, lb, "Dim2 (research design)")
            print_disagreements(res["dim3_disagree"], la, lb, "Dim3 (evidence strength)")

    # Distribution of codes across models (on N-way overlap set)
    overlap_set = nway_overlap if len(model_keys) >= 2 else set(next(iter(ids.values()))) if ids else set()
    if overlap_set:
        print()
        print("=" * 80)
        overlap_label = f"{len(model_keys)}-WAY" if len(model_keys) >= 2 else "SINGLE-MODEL"
        print(f"CODE DISTRIBUTIONS ON {overlap_label} OVERLAP SET (N={len(overlap_set)})")
        print("=" * 80)
        for dim_key, dim_label in [("dim1", "Dim1 (biomarker use)"), ("dim2", "Dim2 (research design)"), ("dim3", "Dim3 (evidence strength)")]:
            print(f"\n  {dim_label}:")
            for mk in model_keys:
                dist = Counter(all_grades[mk][aid][dim_key] for aid in overlap_set)
                top = dist.most_common(8)
                ml = MODEL_LABELS.get(mk, mk)
                print(f"    {ml:30s}: ", end="")
                parts = [f"{code} ({cnt})" for code, cnt in top]
                print(", ".join(parts))

    print()


if __name__ == "__main__":
    main()
