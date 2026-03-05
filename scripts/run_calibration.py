"""
Run LLM grader on calibration examples and save results.

Usage:
    python3 scripts/run_calibration.py
    python3 scripts/run_calibration.py --model google/gemini-2.0-flash-001
    python3 scripts/run_calibration.py --limit 5  # test with first 5 only
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path so we can import grader_prompt
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.grader_prompt import create_grading_prompt, call_openrouter
from scripts.utils import load_env, parse_llm_json


def run_calibration(
    model: str = "google/gemini-2.0-flash-001",
    limit: int | None = None,
    delay: float = 1.0,
):
    """Grade calibration examples and save results."""

    # Load API key
    load_env()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)

    # Load calibration examples
    cal_path = Path(__file__).parent.parent / "data" / "grader_calibration_examples.csv"
    with open(cal_path) as f:
        reader = csv.DictReader(f)
        examples = list(reader)

    if limit:
        examples = examples[:limit]

    print(f"Running {len(examples)} calibration examples with {model}")
    print(f"{'=' * 70}")

    results = []
    for i, ex in enumerate(examples):
        title = ex["PROJECT_TITLE"]
        abstract = ex["ABSTRACT"]
        matched_terms = ex["MATCHED_TERMS"]
        app_id = ex["APPLICATION_ID"]

        print(f"\n[{i+1}/{len(examples)}] {app_id}: {title[:60]}...")
        print(f"  Matched terms: {matched_terms}")

        messages = create_grading_prompt(title, abstract)

        try:
            response = call_openrouter(messages, model, api_key)
            content = response["choices"][0]["message"]["content"]
            parsed = parse_llm_json(content)

            print(f"  biomarker_use: {parsed.get('biomarker_use', {}).get('primary', '?')}"
                  f" (conf: {parsed.get('biomarker_use', {}).get('confidence', '?')})")
            print(f"  research_design: {parsed.get('research_design', {}).get('primary', '?')}")
            print(f"  evidence_strength: {parsed.get('evidence_strength', {}).get('code', '?')}")
            print(f"  reasoning: {parsed.get('reasoning', '')[:100]}...")

            results.append({
                "application_id": app_id,
                "year": ex["YEAR"],
                "title": title,
                "matched_terms": matched_terms,
                "model": model,
                "classification": parsed,
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "application_id": app_id,
                "year": ex["YEAR"],
                "title": title,
                "matched_terms": matched_terms,
                "model": model,
                "error": str(e),
            })

        # Rate limiting
        if i < len(examples) - 1:
            time.sleep(delay)

    # Save results
    model_slug = model.split("/")[-1]
    output_path = Path(__file__).parent.parent / "data" / f"calibration_results_{model_slug}.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n{'=' * 70}")
    print(f"Results saved to {output_path}")

    # Summary
    print(f"\n## Summary ({len(results)} examples)")
    use_counts: dict[str, int] = {}
    for r in results:
        if "classification" in r:
            code = r["classification"].get("biomarker_use", {}).get("primary", "ERROR")
        else:
            code = "ERROR"
        use_counts[code] = use_counts.get(code, 0) + 1

    for code, count in sorted(use_counts.items(), key=lambda x: -x[1]):
        print(f"  {code}: {count}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/gemini-2.0-flash-001")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    run_calibration(model=args.model, limit=args.limit, delay=args.delay)
