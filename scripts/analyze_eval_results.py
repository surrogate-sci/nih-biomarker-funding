"""
Analyze grading results from Inspect AI .eval log files.

Reads .eval files (journal-based ZIP archives without central directory) directly,
extracts per-sample scores and metadata, and prints distribution tables.

Usage:
    python3 scripts/analyze_eval_results.py logs/nci-v31-gpt-oss-120b/
    python3 scripts/analyze_eval_results.py logs/nci-v31-gpt-oss-120b/ logs/nci-v31-gemini-flash-lite/
    python3 scripts/analyze_eval_results.py logs/  # all .eval files recursively
"""

import argparse
import collections
import json
import struct
import zlib
from pathlib import Path

LOCAL_FILE_HEADER_SIG = b"PK\x03\x04"


def iter_journal_entries(path: Path):
    """Yield (filename, parsed_dict) from a journal-based .eval ZIP.

    .eval files are written as streaming ZIP archives: local file entries exist
    but the central directory (EOCD) is never written, so standard zipfile
    readers fail. We parse local file headers directly.
    """
    with open(path, "rb") as f:
        data = f.read()

    offset = 0
    while offset < len(data) - 30:
        if data[offset : offset + 4] != LOCAL_FILE_HEADER_SIG:
            offset += 1
            continue
        try:
            (
                _,
                _flags,
                compression,
                _mod_time,
                _mod_date,
                _crc32,
                compressed_size,
                _uncompressed_size,
                fname_len,
                extra_len,
            ) = struct.unpack_from("<HHHHHiIIHH", data, offset + 4)

            fname_start = offset + 30
            fname = data[fname_start : fname_start + fname_len].decode(
                "utf-8", errors="replace"
            )
            data_start = fname_start + fname_len + extra_len

            if compressed_size > 0 and data_start + compressed_size <= len(data):
                raw_bytes = data[data_start : data_start + compressed_size]
                if compression == 8:  # deflate
                    raw_bytes = zlib.decompress(raw_bytes, -15)
                try:
                    yield fname, json.loads(raw_bytes)
                except json.JSONDecodeError:
                    pass  # skip malformed entries

            offset = data_start + max(compressed_size, 1)
        except struct.error:
            offset += 1


def load_eval_log(path: Path) -> dict:
    """Load all samples and header from one .eval file.

    Returns a dict with:
      - model: str
      - eval_id: str
      - samples: list of sample dicts
      - errors: count of samples with errors
      - path: Path
    """
    result = {
        "path": path,
        "model": "unknown",
        "eval_id": "unknown",
        "dataset": "unknown",
        "samples": [],
        "error_count": 0,
    }

    for fname, obj in iter_journal_entries(path):
        if fname == "_journal/start.json":
            eval_info = obj.get("eval", {})
            result["model"] = eval_info.get("model", "unknown")
            result["eval_id"] = eval_info.get("eval_id", "unknown")
            dataset = eval_info.get("task_args", {}).get("dataset_path", "unknown")
            result["dataset"] = Path(dataset).name if dataset != "unknown" else "unknown"
        elif fname.startswith("samples/"):
            if obj.get("error"):
                result["error_count"] += 1
            else:
                result["samples"].append(obj)

    return result


def extract_scores(sample: dict) -> dict | None:
    """Extract rubric_scorer scores and metadata from a sample dict."""
    scorer_result = sample.get("scores", {}).get("rubric_scorer")
    if not scorer_result:
        return None

    value = scorer_result.get("value", {})
    meta = scorer_result.get("metadata", {})

    return {
        "sample_id": sample.get("id"),
        "valid_json": value.get("valid_json", 0.0),
        "valid_codes": value.get("valid_codes", 0.0),
        "dim1_primary": meta.get("dim1_primary"),
        "dim1_secondary": meta.get("dim1_secondary"),
        "dim1_confidence": meta.get("dim1_confidence"),
        "dim2_primary": meta.get("dim2_primary"),
        "dim2_secondary": meta.get("dim2_secondary"),
        "dim2_confidence": meta.get("dim2_confidence"),
        "dim3_code": meta.get("dim3_code"),
        "dim3_confidence": meta.get("dim3_confidence"),
        "invalid_codes": meta.get("invalid_codes", []),
        "fy": sample.get("metadata", {}).get("fy"),
        "activity": sample.get("metadata", {}).get("activity"),
        "explicit_biomarker": sample.get("metadata", {}).get("explicit_biomarker"),
        "has_abstract": sample.get("metadata", {}).get("has_abstract"),
    }


def print_counter_table(counter: collections.Counter, title: str, total: int) -> None:
    print(f"\n  {title}")
    print(f"  {'Code':<35} {'N':>6}  {'%':>6}")
    print(f"  {'-'*35} {'-'*6}  {'-'*6}")
    for code, n in counter.most_common():
        pct = 100 * n / total if total else 0
        label = code if code is not None else "(null)"
        print(f"  {label:<35} {n:>6}  {pct:>5.1f}%")


def analyze_log(log: dict) -> None:
    total_entries = len(log["samples"]) + log["error_count"]
    scored = [s for s in log["samples"] if extract_scores(s) is not None]
    rows = [extract_scores(s) for s in scored]

    print(f"\n{'='*60}")
    print(f"  Log: {log['path'].name}")
    print(f"  Model: {log['model']}")
    print(f"  Dataset: {log['dataset']}")
    print(f"{'='*60}")
    print(f"\n  Sample counts")
    print(f"    Total journal entries : {total_entries}")
    print(f"    API errors            : {log['error_count']}")
    print(f"    Completed (no error)  : {len(log['samples'])}")
    print(f"    With rubric scores    : {len(rows)}")

    if not rows:
        print("\n  No scored samples to analyze.")
        return

    n = len(rows)
    valid_json_rate = sum(r["valid_json"] for r in rows) / n
    valid_codes_rate = sum(r["valid_codes"] for r in rows) / n
    print(f"\n  Score quality")
    print(f"    valid_json  : {valid_json_rate:.1%}  ({int(valid_json_rate*n)}/{n})")
    print(f"    valid_codes : {valid_codes_rate:.1%}  ({int(valid_codes_rate*n)}/{n})")

    invalid_dim_counts = collections.Counter()
    for r in rows:
        for dim in r["invalid_codes"]:
            invalid_dim_counts[dim] += 1
    if invalid_dim_counts:
        print(f"\n  Invalid code breakdown by dimension")
        for dim, cnt in sorted(invalid_dim_counts.items()):
            print(f"    {dim}: {cnt}")

    # Dim1
    dim1 = collections.Counter(r["dim1_primary"] for r in rows)
    print_counter_table(dim1, "Dimension 1 — Biomarker Use (primary)", n)

    # Dim2 (only for non-not_applicable)
    dim2_rows = [r for r in rows if r["dim1_primary"] != "not_applicable"]
    if dim2_rows:
        dim2 = collections.Counter(r["dim2_primary"] for r in dim2_rows)
        print_counter_table(
            dim2,
            f"Dimension 2 — Research Design (primary, n={len(dim2_rows)} excl. not_applicable)",
            len(dim2_rows),
        )

    # Dim3
    dim3_rows = [r for r in rows if r["dim1_primary"] != "not_applicable"]
    if dim3_rows:
        dim3 = collections.Counter(r["dim3_code"] for r in dim3_rows)
        print_counter_table(
            dim3,
            f"Dimension 3 — Evidence Strength (n={len(dim3_rows)} excl. not_applicable)",
            len(dim3_rows),
        )

    # Confidence breakdown
    for dim_label, conf_key in [
        ("Dim1", "dim1_confidence"),
        ("Dim2", "dim2_confidence"),
        ("Dim3", "dim3_confidence"),
    ]:
        conf_rows = (
            [r for r in rows if r["dim1_primary"] != "not_applicable"]
            if dim_label != "Dim1"
            else rows
        )
        conf = collections.Counter(r[conf_key] for r in conf_rows)
        print_counter_table(
            conf,
            f"{dim_label} confidence (n={len(conf_rows)})",
            len(conf_rows),
        )

    # Activity type breakdown
    activity = collections.Counter(r["activity"] for r in rows)
    print_counter_table(activity, "Activity type", n)

    # Explicit biomarker
    explicit = collections.Counter(r["explicit_biomarker"] for r in rows)
    print(f"\n  Explicit biomarker flag")
    for k, cnt in sorted(explicit.items(), key=lambda x: str(x[0])):
        print(f"    {str(k):<10}: {cnt:>6}  ({100*cnt/n:.1f}%)")


def find_eval_files(paths: list[Path]) -> list[Path]:
    """Expand directories recursively; pass through .eval files directly."""
    result = []
    for p in paths:
        if p.is_dir():
            result.extend(sorted(p.rglob("*.eval")))
        elif p.suffix == ".eval":
            result.append(p)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Analyze grading results from Inspect AI .eval log files."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help=".eval files or directories containing .eval files",
    )
    parser.add_argument(
        "--skip-errors",
        action="store_true",
        help="Skip logs where all samples have errors",
    )
    args = parser.parse_args()

    eval_files = find_eval_files(args.paths)
    if not eval_files:
        print("No .eval files found.")
        return

    print(f"Found {len(eval_files)} .eval file(s)")

    for path in eval_files:
        log = load_eval_log(path)
        if args.skip_errors and len(log["samples"]) == 0:
            print(f"\n[skipping {path.name} — no completed samples]")
            continue
        analyze_log(log)


if __name__ == "__main__":
    main()
