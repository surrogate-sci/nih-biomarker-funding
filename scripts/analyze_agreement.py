#!/usr/bin/env python3
"""Analyze inter-rater agreement between LLM graders on oncology grants."""

import json
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

FILES = {
    "gemini": DATA_DIR / "oncology_grades_gemini-2.5-flash-lite.jsonl",
    "gpt4o-mini": DATA_DIR / "oncology_grades_gpt-4o-mini.jsonl",
    "gpt41-mini": DATA_DIR / "oncology_grades_gpt-4.1-mini.jsonl",
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
    # Load all files
    all_grades = {}
    print("=" * 80)
    print("LLM GRADER AGREEMENT ANALYSIS — NIH Biomarker Oncology Grants")
    print("=" * 80)
    print()

    for key, path in FILES.items():
        grades, errors = load_grades(path)
        all_grades[key] = grades
        print(f"  {MODEL_LABELS[key]:30s}: {len(grades):5d} valid grades, {errors} errors")

    print()

    # Find overlaps
    ids = {k: set(v.keys()) for k, v in all_grades.items()}
    triple = ids["gemini"] & ids["gpt4o-mini"] & ids["gpt41-mini"]
    gem_4o = ids["gemini"] & ids["gpt4o-mini"]
    gem_41 = ids["gemini"] & ids["gpt41-mini"]
    pair_4o_41 = ids["gpt4o-mini"] & ids["gpt41-mini"]

    print("OVERLAP COUNTS")
    print("-" * 50)
    print(f"  All three models:              {len(triple):5d}")
    print(f"  Gemini + GPT-4o-mini:          {len(gem_4o):5d}")
    print(f"  Gemini + GPT-4.1-mini:         {len(gem_41):5d}")
    print(f"  GPT-4o-mini + GPT-4.1-mini:    {len(pair_4o_41):5d}")
    print()

    # Pairwise agreement
    pairs = [
        ("gemini", "gpt4o-mini", gem_4o),
        ("gemini", "gpt41-mini", gem_41),
        ("gpt4o-mini", "gpt41-mini", pair_4o_41),
    ]

    print("=" * 80)
    print("PAIRWISE AGREEMENT RATES")
    print("=" * 80)
    print()
    print(f"  {'Pair':42s}   {'N':>5s}   {'Dim1':>6s}   {'Dim2':>6s}   {'Dim3':>6s}")
    print(f"  {'-'*42}   {'-----':>5s}   {'------':>6s}   {'------':>6s}   {'------':>6s}")

    pair_results = {}
    for ka, kb, common in pairs:
        res = compute_agreement(
            all_grades[ka], all_grades[kb],
            MODEL_LABELS[ka], MODEL_LABELS[kb],
            common,
        )
        pair_results[(ka, kb)] = res
        label = f"{MODEL_LABELS[ka]} vs {MODEL_LABELS[kb]}"
        print(
            f"  {label:42s}   {res['n']:5d}   {res['dim1_rate']:5.1%}   {res['dim2_rate']:5.1%}   {res['dim3_rate']:5.1%}"
        )

    print()

    # Triple agreement
    print("=" * 80)
    print("THREE-WAY AGREEMENT (all three models must agree)")
    print("=" * 80)
    tres = compute_triple_agreement(all_grades, triple)
    print(f"  N = {tres['n']}")
    print(f"  Dim1 (biomarker use):   {tres['dim1_rate']:5.1%}")
    print(f"  Dim2 (research design): {tres['dim2_rate']:5.1%}")
    print(f"  Dim3 (evidence str.):   {tres['dim3_rate']:5.1%}")
    print()

    # Disagreement details
    print("=" * 80)
    print("DISAGREEMENT PATTERNS (top 5 per dimension per pair)")
    print("=" * 80)
    for ka, kb, common in pairs:
        res = pair_results[(ka, kb)]
        la, lb = MODEL_LABELS[ka], MODEL_LABELS[kb]
        print(f"\n  --- {la} vs {lb} (N={res['n']}) ---")
        print_disagreements(res["dim1_disagree"], la, lb, "Dim1 (biomarker use)")
        print_disagreements(res["dim2_disagree"], la, lb, "Dim2 (research design)")
        print_disagreements(res["dim3_disagree"], la, lb, "Dim3 (evidence strength)")

    # Distribution of codes across models (on triple-overlap set)
    print()
    print("=" * 80)
    print("CODE DISTRIBUTIONS ON TRIPLE-OVERLAP SET (N={})".format(len(triple)))
    print("=" * 80)
    for dim_key, dim_label in [("dim1", "Dim1 (biomarker use)"), ("dim2", "Dim2 (research design)"), ("dim3", "Dim3 (evidence strength)")]:
        print(f"\n  {dim_label}:")
        for mk in ["gemini", "gpt4o-mini", "gpt41-mini"]:
            dist = Counter(all_grades[mk][aid][dim_key] for aid in triple)
            top = dist.most_common(8)
            print(f"    {MODEL_LABELS[mk]:30s}: ", end="")
            parts = [f"{code} ({cnt})" for code, cnt in top]
            print(", ".join(parts))

    print()


if __name__ == "__main__":
    main()
