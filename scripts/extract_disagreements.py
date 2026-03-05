#!/usr/bin/env python3
"""Extract specific disagreement patterns across model grades for rubric refinement.

Loads JSONL grade files from three models, finds grants graded by 2+ models,
and extracts examples of predefined disagreement patterns.

Outputs:
  - data/disagreement_examples.json  (structured, with reasoning)
  - data/disagreement_examples.csv   (flat, for quick review)
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

GRADE_FILES = {
    "gemini-2.5-flash-lite": DATA_DIR / "oncology_grades_gemini-2.5-flash-lite.jsonl",
    "gpt-4o-mini": DATA_DIR / "oncology_grades_gpt-4o-mini.jsonl",
    "gpt-4.1-mini": DATA_DIR / "oncology_grades_gpt-4.1-mini.jsonl",
}

# (dimension_key, code_a, code_b)
# dimension_key maps to the path in the classification dict
PATTERNS = [
    ("dim1", "diagnostic", "susceptibility_risk"),
    ("dim1", "prognostic_risk", "prognostic_efficacy"),
    ("dim1", "methods_correlational", "methods_causal"),
    ("dim2", "observational_retrospective", "observational_cohort"),
    ("dim2", "experimental_singlearm", "experimental_rct"),
    ("dim3", "correlational", "experimental_weak"),
    ("dim3", "causal_preclinical", "experimental_weak"),
    ("dim3", "methods_for_causal", "correlational"),
]

MAX_EXAMPLES = 5


def load_grades() -> dict[str, dict[str, dict]]:
    """Load all grade files. Returns {application_id: {model_name: record}}."""
    grants: dict[str, dict[str, dict]] = defaultdict(dict)
    for model_name, path in GRADE_FILES.items():
        if not path.exists():
            print(f"WARNING: {path} not found, skipping", file=sys.stderr)
            continue
        with open(path) as f:
            for line in f:
                rec = json.loads(line)
                # Skip error records
                if "error" in rec or rec.get("classification") is None:
                    continue
                app_id = str(rec["application_id"])
                grants[app_id][model_name] = rec
    return grants


def extract_code(rec: dict, dimension: str) -> str | None:
    """Extract the primary code for a dimension from a record's classification."""
    cls = rec.get("classification", {})
    if dimension == "dim1":
        return cls.get("biomarker_use", {}).get("primary")
    elif dimension == "dim2":
        return cls.get("research_design", {}).get("primary")
    elif dimension == "dim3":
        return cls.get("evidence_strength", {}).get("code")
    return None


def extract_all_codes(rec: dict) -> dict:
    """Extract dim1, dim2, dim3 primary codes from a record."""
    return {
        "dim1": extract_code(rec, "dim1"),
        "dim2": extract_code(rec, "dim2"),
        "dim3": extract_code(rec, "dim3"),
    }


def build_model_entry(rec: dict) -> dict:
    """Build the per-model entry for an example."""
    codes = extract_all_codes(rec)
    codes["reasoning"] = rec.get("classification", {}).get("reasoning", "")
    return codes


def find_pattern_examples(
    grants: dict[str, dict[str, dict]],
    dimension: str,
    code_a: str,
    code_b: str,
) -> tuple[int, list[dict]]:
    """Find grants where models disagree on the given pattern.

    Returns (total_disagreements, up_to_5_examples).
    """
    matches = []
    for app_id, model_grades in grants.items():
        if len(model_grades) < 2:
            continue
        codes_by_model = {
            m: extract_code(r, dimension) for m, r in model_grades.items()
        }
        code_set = set(codes_by_model.values())
        if code_a in code_set and code_b in code_set:
            # At least one model says code_a and another says code_b
            title = next(iter(model_grades.values())).get("title", "")
            example = {
                "application_id": app_id,
                "title": title,
                "models": {
                    m: build_model_entry(r) for m, r in model_grades.items()
                },
            }
            matches.append(example)

    return len(matches), matches[:MAX_EXAMPLES]


def main():
    grants = load_grades()

    # Filter to grants with 2+ models
    multi_model = {k: v for k, v in grants.items() if len(v) >= 2}
    print(f"Loaded {len(grants)} unique grants, {len(multi_model)} graded by 2+ models\n")

    results = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "total_grants_multi_model": len(multi_model),
        "patterns": [],
    }

    csv_rows = []
    model_names = ["gemini-2.5-flash-lite", "gpt-4o-mini", "gpt-4.1-mini"]

    print(f"{'Pattern':<55} {'Total':>6} {'Extracted':>9}")
    print("-" * 72)

    for dimension, code_a, code_b in PATTERNS:
        total, examples = find_pattern_examples(multi_model, dimension, code_a, code_b)
        pattern_label = f"{dimension}: {code_a} vs {code_b}"
        print(f"{pattern_label:<55} {total:>6} {len(examples):>9}")

        results["patterns"].append(
            {
                "dimension": dimension,
                "code_a": code_a,
                "code_b": code_b,
                "total_disagreements": total,
                "examples": examples,
            }
        )

        for ex in examples:
            row = {
                "pattern": pattern_label,
                "application_id": ex["application_id"],
                "title": ex["title"],
            }
            for m in model_names:
                prefix = {
                    "gemini-2.5-flash-lite": "gemini",
                    "gpt-4o-mini": "gpt4o",
                    "gpt-4.1-mini": "gpt41",
                }[m]
                if m in ex["models"]:
                    row[f"{prefix}_dim1"] = ex["models"][m].get("dim1", "")
                    row[f"{prefix}_dim2"] = ex["models"][m].get("dim2", "")
                    row[f"{prefix}_dim3"] = ex["models"][m].get("dim3", "")
                else:
                    row[f"{prefix}_dim1"] = ""
                    row[f"{prefix}_dim2"] = ""
                    row[f"{prefix}_dim3"] = ""
            csv_rows.append(row)

    # Save JSON
    json_path = DATA_DIR / "disagreement_examples.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON saved to {json_path}")

    # Save CSV
    csv_path = DATA_DIR / "disagreement_examples.csv"
    fieldnames = [
        "pattern",
        "application_id",
        "title",
        "gemini_dim1",
        "gemini_dim2",
        "gemini_dim3",
        "gpt4o_dim1",
        "gpt4o_dim2",
        "gpt4o_dim3",
        "gpt41_dim1",
        "gpt41_dim2",
        "gpt41_dim3",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"CSV saved to {csv_path}")

    total_examples = sum(len(p["examples"]) for p in results["patterns"])
    print(f"\nTotal examples extracted: {total_examples}")


if __name__ == "__main__":
    main()
