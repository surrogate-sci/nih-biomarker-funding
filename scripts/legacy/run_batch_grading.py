"""
Batch LLM grading of sampled grants with checkpoint/resume support.

Runs a single model against all grants in a sample CSV. Use JSONL output
for streaming writes and safe resume. Run once per model.

Usage:
    python3 scripts/run_batch_grading.py \
        --sample data/oncology_sample_100per_year.csv \
        --model google/gemini-2.5-flash-lite \
        --output data/oncology_grades_gemini-2.5-flash-lite.jsonl

    # Smoke test
    python3 scripts/run_batch_grading.py \
        --sample data/oncology_sample_100per_year.csv \
        --model google/gemini-2.5-flash-lite \
        --output data/oncology_grades_gemini-2.5-flash-lite.jsonl \
        --limit 10
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path so we can import grader_prompt
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.grader_prompt import call_openai, call_openrouter, create_grading_prompt
from scripts.utils import load_env, parse_llm_json


def load_sample(csv_path: Path) -> list[dict]:
    """Load sample CSV, filtering to rows with abstracts."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("HAS_ABSTRACT", "").strip() == "True":
                rows.append(row)
    return rows


def load_checkpoint(output_path: Path) -> set[str]:
    """Read existing JSONL to find already-graded APPLICATION_IDs."""
    done: set[str] = set()
    if not output_path.exists():
        return done
    with open(output_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                app_id = record.get("application_id", "")
                if app_id and "error" not in record:
                    done.add(app_id)
            except json.JSONDecodeError:
                continue
    return done


def grade_one(
    title: str, abstract: str, model: str, api_key: str, api: str = "openrouter"
) -> dict:
    """Grade a single grant. Returns parsed classification or error dict."""
    messages = create_grading_prompt(title, abstract)
    if api == "openai":
        # Direct OpenAI: strip provider prefix (e.g. "openai/gpt-4.1-mini" -> "gpt-4.1-mini")
        model_id = model.split("/", 1)[-1] if "/" in model else model
        response = call_openai(messages, model_id, api_key)
    else:
        response = call_openrouter(messages, model, api_key)
    content = response["choices"][0]["message"]["content"]
    return parse_llm_json(content)


def run_batch(
    sample_path: Path,
    output_path: Path,
    model: str,
    delay: float = 1.0,
    limit: int | None = None,
    api: str = "openrouter",
):
    """Grade all ungraded grants in the sample."""
    load_env()
    if api == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: OPENAI_API_KEY not set in .env")
            sys.exit(1)
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print("ERROR: OPENROUTER_API_KEY not set in .env")
            sys.exit(1)

    print(f"Loading sample from {sample_path}...")
    all_rows = load_sample(sample_path)
    print(f"  {len(all_rows)} rows with abstracts")

    checkpoint = load_checkpoint(output_path)
    if checkpoint:
        print(f"  Resuming: {len(checkpoint)} already graded")

    # Filter to ungraded rows
    todo = [r for r in all_rows if r["APPLICATION_ID"].strip() not in checkpoint]
    if limit:
        todo = todo[:limit]

    print(f"  Grading {len(todo)} grants with {model}")
    print(f"{'=' * 70}")

    errors = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, row in enumerate(todo):
            app_id = row["APPLICATION_ID"].strip()
            fy = row["FY"].strip()
            title = row["PROJECT_TITLE"].strip()

            print(f"[{i + 1}/{len(todo)}] {app_id} (FY{fy}): {title[:50]}...", end=" ")

            record = {
                "application_id": app_id,
                "fy": fy,
                "title": title,
                "model": model,
            }

            try:
                classification = grade_one(
                    title, row["ABSTRACT_TEXT"], model, api_key, api
                )
                record["classification"] = classification
                dim1 = classification.get("biomarker_use", {}).get("primary", "?")
                print(f"→ {dim1}")
            except Exception as e:
                record["error"] = str(e)
                errors += 1
                print(f"→ ERROR: {e}")

            out_f.write(json.dumps(record) + "\n")
            out_f.flush()

            # Rate limiting (skip after last item)
            if i < len(todo) - 1:
                time.sleep(delay)

    print(f"\n{'=' * 70}")
    print(f"Done. Graded {len(todo)} grants ({errors} errors)")
    print(f"Results appended to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch LLM grading with checkpointing")
    parser.add_argument(
        "--sample",
        required=True,
        help="Path to sample CSV (from sample_oncology.py)",
    )
    parser.add_argument(
        "--model",
        default="google/gemini-2.5-flash-lite",
        help="OpenRouter model ID",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSONL path",
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Seconds between API calls"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max grants to grade (for testing)"
    )
    parser.add_argument(
        "--api",
        choices=["openrouter", "openai"],
        default="openrouter",
        help="API backend: 'openrouter' (default) or 'openai' (direct, needs OPENAI_API_KEY)",
    )
    args = parser.parse_args()

    run_batch(
        sample_path=Path(args.sample),
        output_path=Path(args.output),
        model=args.model,
        delay=args.delay,
        limit=args.limit,
        api=args.api,
    )


if __name__ == "__main__":
    main()
