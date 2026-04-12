# NCI Pilot Analysis Pipeline + Rubric Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `analysis/nci-pilot/` as a curated, always show-ready pipeline for NCI grading results, and create a two-level rubric design skill hierarchy (user-level psychometric principles + project-level application).

**Architecture:** `analysis/nci-pilot/config.yaml` designates canonical run IDs; `extract.py` reads those `.eval` files and produces small per-grant CSVs in `results/`; `analyze.py` reads those CSVs and produces charts and `SUMMARY.md`. The two rubric skills live at `~/.claude/skills/rubric-design/` (user-level, general methodology) and `.claude/skills/rubric/` (project-level, applies the methodology to this project).

**Tech Stack:** Python 3.11+, PyYAML, pandas, seaborn/matplotlib (charts), existing `scripts/analyze_eval_results.py` (`.eval` parsing), Makefile for orchestration.

**Context for the implementing agent:**
- Working directory is the project root: `/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/` (or a worktree of it)
- `.eval` files are journal-based ZIP archives without a central directory — use `iter_journal_entries` / `load_eval_log` from `scripts/analyze_eval_results.py`, do NOT use Python's `zipfile` module
- `data/` and `logs/` are gitignored; use `git add -f` when committing files under those paths
- Project venv: `.venv/bin/python` (run tests with `.venv/bin/python -m pytest` or `.venv/bin/python -m unittest`)
- RUBRIC.md is scientific content — do not edit it without Manjari's direction
- See `CLAUDE.md` for full project context

---

## Task 1: Fix `scripts/run-grading.sh` — worktree venv path

**Problem:** The script computes `REPO_ROOT` as the directory containing the script. In git worktrees (e.g. `.claude/worktrees/silly-kare/`), this is the worktree root, which has no `.venv` or `.env`. The main repo's `.venv` and `.env` must be used.

**Files:**
- Modify: `scripts/run-grading.sh`

**Step 1: Read the current script**

```bash
cat scripts/run-grading.sh
```

**Step 2: Replace the `INSPECT` and `ENV_FILE` lines**

Find the lines:
```bash
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSPECT="$REPO_ROOT/.venv/bin/inspect"
ENV_FILE="$REPO_ROOT/.env"
```

Replace with:
```bash
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# In git worktrees, .venv and .env live in the main repo, not the worktree.
# Use git to find the main repo root.
GIT_DIR=$(git -C "$REPO_ROOT" rev-parse --absolute-git-dir 2>/dev/null || echo "$REPO_ROOT/.git")
if [[ "$GIT_DIR" == *"/worktrees/"* ]]; then
    MAIN_ROOT="${GIT_DIR%%/.git/worktrees/*}"
else
    MAIN_ROOT="$(dirname "$GIT_DIR")"
fi
INSPECT="$MAIN_ROOT/.venv/bin/inspect"
ENV_FILE="$MAIN_ROOT/.env"
```

**Step 3: Verify the fix manually**

```bash
# From the worktree:
bash scripts/run-grading.sh --model google/gemini-2.5-flash-lite --help 2>&1 || true
# Should print usage, NOT "No such file or directory"
```

**Step 4: Commit**

```bash
git add scripts/run-grading.sh
git commit -m "fix: run-grading.sh finds .venv in main repo when run from worktree"
```

---

## Task 2: Create `analysis/nci-pilot/` skeleton and `config.yaml`

**Files:**
- Create: `analysis/nci-pilot/config.yaml`
- Create: `analysis/nci-pilot/results/.gitkeep`
- Create: `analysis/nci-pilot/charts/.gitkeep`
- Modify: `.gitignore` (if charts/ should be gitignored — see Step 2)

**Step 1: Create the directory structure**

```bash
mkdir -p analysis/nci-pilot/results
mkdir -p analysis/nci-pilot/charts
touch analysis/nci-pilot/results/.gitkeep
touch analysis/nci-pilot/charts/.gitkeep
```

**Step 2: Decide chart gitignore policy**

Charts are generated from committed CSVs — they can be regenerated. Commit `results/*.csv` and `SUMMARY.md`; gitignore `charts/` to keep the repo lean. Add to the project `.gitignore`:

```
analysis/nci-pilot/charts/
```

(Check whether a project-level `.gitignore` exists or append to the root one.)

**Step 3: Create `analysis/nci-pilot/config.yaml`**

```yaml
# Canonical run registry for analysis/nci-pilot/.
# Edit this file to designate which runs are the current best results.
# Run `make extract` after editing to regenerate results/.

canonical_runs:
  gemini_2.5_flash_lite:
    run_id: 8erjM2hN9MQ5kE5LQvnP7L
    log_path: logs/nci-v31-gemini-flash-lite/2026-04-12T15-06-44-00-00_biomarker-grading_8erjM2hN9MQ5kE5LQvnP7L.eval
    model: google/gemini-2.5-flash-lite
    rubric_version: f6ecad8
    note: "full NCI v3.1, pre-disease_non_biomarker"
  gpt_oss_120b:
    run_id: hbNMjdEnGVXJ5YWcsKHfcQ
    log_path: logs/nci-v31-gpt-oss-120b/2026-04-12T15-48-59-00-00_biomarker-grading_hbNMjdEnGVXJ5YWcsKHfcQ.eval
    model: together/openai/gpt-oss-120b
    rubric_version: 60d21e7
    note: "full NCI v3.1, pre-disease_non_biomarker"
```

**Step 4: Commit skeleton**

```bash
git add analysis/nci-pilot/config.yaml analysis/nci-pilot/results/.gitkeep analysis/nci-pilot/charts/.gitkeep .gitignore
git commit -m "analysis: scaffold nci-pilot directory with config.yaml and canonical run registry"
```

---

## Task 3: Write `extract.py` — `.eval` files → per-grant CSVs (TDD)

**Purpose:** For each canonical run in `config.yaml`, read the `.eval` file, extract per-sample scores and metadata, write to `analysis/nci-pilot/results/{run_label}.csv`.

**Output CSV columns** (no text fields — metadata + scores only):
```
application_id, fy, ic, activity, total_cost, explicit_biomarker,
dim1, dim1_secondary, dim1_confidence,
dim2, dim2_secondary, dim2_confidence,
dim3, dim3_confidence,
valid_json, valid_codes
```

**Files:**
- Create: `analysis/nci-pilot/extract.py`
- Create: `tests/test_nci_pilot_extract.py`

**Step 1: Write the failing test**

```python
# tests/test_nci_pilot_extract.py
"""Tests for analysis/nci-pilot/extract.py"""
import csv
import sys
import unittest
from pathlib import Path

# Make analysis/nci-pilot importable
sys.path.insert(0, str(Path(__file__).parent.parent / "analysis" / "nci-pilot"))

from extract import extract_run, RESULT_COLUMNS


class TestExtractRun(unittest.TestCase):
    """Tests for extract_run() using the 25-sample trial .eval as fixture."""

    FIXTURE_EVAL = Path("logs/test-nci-trial/2026-04-12T15-00-29-00-00_biomarker-grading_5WdUxoX3FxEQRMWcCWs4rA.eval")

    def setUp(self):
        if not self.FIXTURE_EVAL.exists():
            self.skipTest(f"Fixture .eval not found: {self.FIXTURE_EVAL}")

    def test_returns_list_of_dicts(self):
        rows = extract_run(self.FIXTURE_EVAL)
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

    def test_columns_match_spec(self):
        rows = extract_run(self.FIXTURE_EVAL)
        self.assertEqual(set(rows[0].keys()), set(RESULT_COLUMNS))

    def test_application_id_populated(self):
        rows = extract_run(self.FIXTURE_EVAL)
        for row in rows:
            self.assertIsNotNone(row["application_id"])
            self.assertNotEqual(row["application_id"], "")

    def test_dim1_populated_for_valid_rows(self):
        rows = extract_run(self.FIXTURE_EVAL)
        valid_rows = [r for r in rows if r["valid_json"] == 1.0]
        for row in valid_rows:
            self.assertIsNotNone(row["dim1"])

    def test_expected_row_count(self):
        rows = extract_run(self.FIXTURE_EVAL)
        # 25-sample trial should yield 25 rows (or fewer if some errored)
        self.assertLessEqual(len(rows), 25)
        self.assertGreaterEqual(len(rows), 20)  # expect at most a few errors
```

**Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_nci_pilot_extract.py -v
```
Expected: `ModuleNotFoundError: No module named 'extract'`

**Step 3: Implement `analysis/nci-pilot/extract.py`**

```python
"""Extract per-grant scores from canonical .eval files → results/*.csv.

Usage:
    python analysis/nci-pilot/extract.py               # uses config.yaml
    python analysis/nci-pilot/extract.py --run gemini_2.5_flash_lite
"""

import csv
import sys
from pathlib import Path

import yaml

# Import .eval parsing from project scripts
_SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))
from analyze_eval_results import load_eval_log  # noqa: E402

RESULT_COLUMNS = [
    "application_id",
    "fy",
    "ic",
    "activity",
    "total_cost",
    "explicit_biomarker",
    "dim1",
    "dim1_secondary",
    "dim1_confidence",
    "dim2",
    "dim2_secondary",
    "dim2_confidence",
    "dim3",
    "dim3_confidence",
    "valid_json",
    "valid_codes",
]

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent.parent


def extract_run(eval_path: Path) -> list[dict]:
    """Load one .eval file; return list of per-grant dicts."""
    log = load_eval_log(eval_path)
    rows = []
    for sample in log["samples"]:
        scores = sample.get("scores", {}).get("rubric_scorer", {})
        value = scores.get("value", {})
        meta_score = scores.get("metadata", {})
        meta_sample = sample.get("metadata", {})

        rows.append({
            "application_id": sample.get("id"),
            "fy": meta_sample.get("fy"),
            "ic": meta_sample.get("ic"),
            "activity": meta_sample.get("activity"),
            "total_cost": meta_sample.get("total_cost"),
            "explicit_biomarker": meta_sample.get("explicit_biomarker"),
            "dim1": meta_score.get("dim1_primary"),
            "dim1_secondary": meta_score.get("dim1_secondary"),
            "dim1_confidence": meta_score.get("dim1_confidence"),
            "dim2": meta_score.get("dim2_primary"),
            "dim2_secondary": meta_score.get("dim2_secondary"),
            "dim2_confidence": meta_score.get("dim2_confidence"),
            "dim3": meta_score.get("dim3_code"),
            "dim3_confidence": meta_score.get("dim3_confidence"),
            "valid_json": value.get("valid_json"),
            "valid_codes": value.get("valid_codes"),
        })
    return rows


def write_results_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} rows → {out_path}")


def main(run_label: str | None = None) -> None:
    config_path = _HERE / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    runs = config["canonical_runs"]
    if run_label:
        runs = {run_label: runs[run_label]}

    for label, run_cfg in runs.items():
        eval_path = _REPO_ROOT / run_cfg["log_path"]
        if not eval_path.exists():
            print(f"  [skip] {label}: .eval not found at {eval_path}")
            continue
        print(f"Extracting {label} ({run_cfg['model']})...")
        rows = extract_run(eval_path)
        out_path = _HERE / "results" / f"{label}.csv"
        write_results_csv(rows, out_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", help="Extract only this run label")
    args = parser.parse_args()
    main(run_label=args.run)
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_nci_pilot_extract.py -v
```
Expected: All tests PASS.

**Step 5: Run extract on real data to verify output**

```bash
.venv/bin/python analysis/nci-pilot/extract.py
ls analysis/nci-pilot/results/
head -3 analysis/nci-pilot/results/gemini_2.5_flash_lite.csv
```
Expected: Two CSV files, ~3,770 rows each, correct column headers.

**Step 6: Commit**

```bash
git add analysis/nci-pilot/extract.py tests/test_nci_pilot_extract.py
git add -f analysis/nci-pilot/results/gemini_2.5_flash_lite.csv
git add -f analysis/nci-pilot/results/gpt_oss_120b.csv
git commit -m "analysis: add extract.py — .eval → per-grant CSVs for nci-pilot"
```

---

## Task 4: Write `analyze.py` — per-grant CSVs → charts + `SUMMARY.md` (TDD)

**Purpose:** Read all `results/*.csv`, produce charts for all three dimensions (by count and funding, over time, by activity code, inter-model comparison), and write `SUMMARY.md`.

**Files:**
- Create: `analysis/nci-pilot/analyze.py`
- Create: `tests/test_nci_pilot_analyze.py`

**Step 1: Write the failing test**

```python
# tests/test_nci_pilot_analyze.py
"""Tests for analysis/nci-pilot/analyze.py"""
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "analysis" / "nci-pilot"))
from analyze import load_results, build_dim_summary, build_time_series


class TestLoadResults(unittest.TestCase):
    def test_load_returns_dataframe_with_run_label(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test_run.csv"
            p.write_text(
                "application_id,fy,ic,activity,total_cost,explicit_biomarker,"
                "dim1,dim1_secondary,dim1_confidence,dim2,dim2_secondary,"
                "dim2_confidence,dim3,dim3_confidence,valid_json,valid_codes\n"
                "12345,2020,CA,R01,500000,True,diagnostic,,high,"
                "observational_cohort,,medium,correlational,high,1.0,1.0\n"
            )
            df = load_results(Path(tmpdir))
        self.assertIn("run_label", df.columns)
        self.assertEqual(df["run_label"].iloc[0], "test_run")
        self.assertEqual(len(df), 1)


class TestBuildDimSummary(unittest.TestCase):
    def test_summary_has_n_grants_and_total_funding(self):
        df = pd.DataFrame({
            "run_label": ["gemini", "gemini"],
            "dim1": ["diagnostic", "monitoring"],
            "total_cost": [500000.0, 300000.0],
            "valid_json": [1.0, 1.0],
        })
        summary = build_dim_summary(df, dim_col="dim1")
        self.assertIn("n_grants", summary.columns)
        self.assertIn("total_funding", summary.columns)

    def test_excludes_invalid_json_rows(self):
        df = pd.DataFrame({
            "run_label": ["gemini", "gemini"],
            "dim1": ["diagnostic", "diagnostic"],
            "total_cost": [500000.0, 300000.0],
            "valid_json": [1.0, 0.0],
        })
        summary = build_dim_summary(df, dim_col="dim1")
        # Only 1 valid row
        self.assertEqual(summary["n_grants"].sum(), 1)


class TestBuildTimeSeries(unittest.TestCase):
    def test_time_series_groups_by_fy(self):
        df = pd.DataFrame({
            "run_label": ["gemini"] * 3,
            "dim1": ["diagnostic", "diagnostic", "monitoring"],
            "fy": ["2020", "2021", "2020"],
            "total_cost": [100.0, 200.0, 300.0],
            "valid_json": [1.0, 1.0, 1.0],
        })
        ts = build_time_series(df, dim_col="dim1")
        self.assertIn("fy", ts.columns)
        self.assertIn("n_grants", ts.columns)
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_nci_pilot_analyze.py -v
```
Expected: `ModuleNotFoundError: No module named 'analyze'`

**Step 3: Implement `analysis/nci-pilot/analyze.py`**

```python
"""Analyze per-grant CSVs from results/ → charts + SUMMARY.md.

Usage:
    python analysis/nci-pilot/analyze.py
    python analysis/nci-pilot/analyze.py --no-charts   # summary only
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

_HERE = Path(__file__).parent
_RESULTS = _HERE / "results"
_CHARTS = _HERE / "charts"


def load_results(results_dir: Path) -> pd.DataFrame:
    """Load all results CSVs; add run_label column from filename."""
    frames = []
    for csv_path in sorted(results_dir.glob("*.csv")):
        if csv_path.name.startswith("."):
            continue
        df = pd.read_csv(csv_path)
        df["run_label"] = csv_path.stem
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No CSVs found in {results_dir}")
    return pd.concat(frames, ignore_index=True)


def build_dim_summary(df: pd.DataFrame, dim_col: str) -> pd.DataFrame:
    """Aggregate count and funding by dim code and run_label. Excludes invalid_json rows."""
    valid = df[df["valid_json"] == 1.0].copy()
    valid["total_cost"] = pd.to_numeric(valid["total_cost"], errors="coerce").fillna(0)
    summary = (
        valid.groupby(["run_label", dim_col], dropna=False)
        .agg(n_grants=("application_id", "count"), total_funding=("total_cost", "sum"))
        .reset_index()
        .rename(columns={dim_col: "code"})
    )
    return summary


def build_time_series(df: pd.DataFrame, dim_col: str) -> pd.DataFrame:
    """Count and funding by fy × dim code × run_label."""
    valid = df[df["valid_json"] == 1.0].copy()
    valid["total_cost"] = pd.to_numeric(valid["total_cost"], errors="coerce").fillna(0)
    valid["fy"] = valid["fy"].astype(str)
    ts = (
        valid.groupby(["run_label", "fy", dim_col], dropna=False)
        .agg(n_grants=("application_id", "count"), total_funding=("total_cost", "sum"))
        .reset_index()
        .rename(columns={dim_col: "code"})
    )
    return ts


def build_activity_summary(df: pd.DataFrame, dim_col: str) -> pd.DataFrame:
    """Count and funding by activity code × dim code × run_label."""
    valid = df[df["valid_json"] == 1.0].copy()
    valid["total_cost"] = pd.to_numeric(valid["total_cost"], errors="coerce").fillna(0)
    return (
        valid.groupby(["run_label", "activity", dim_col], dropna=False)
        .agg(n_grants=("application_id", "count"), total_funding=("total_cost", "sum"))
        .reset_index()
        .rename(columns={dim_col: "code"})
    )


def make_dim_bar_chart(summary: pd.DataFrame, dim_label: str, out_path: Path) -> None:
    """Grouped bar chart: n_grants by code, hued by run_label."""
    fig, ax = plt.subplots(figsize=(12, 6))
    run_labels = summary["run_label"].unique()
    codes = summary.groupby("code")["n_grants"].sum().sort_values(ascending=False).index
    x = range(len(codes))
    width = 0.8 / len(run_labels)
    for i, label in enumerate(run_labels):
        sub = summary[summary["run_label"] == label].set_index("code")
        vals = [sub.loc[c, "n_grants"] if c in sub.index else 0 for c in codes]
        ax.bar([xi + i * width for xi in x], vals, width=width, label=label)
    ax.set_xticks([xi + width * (len(run_labels) - 1) / 2 for xi in x])
    ax.set_xticklabels(codes, rotation=45, ha="right")
    ax.set_ylabel("Number of grants")
    ax.set_title(f"{dim_label} distribution — NCI pilot (n grants)")
    ax.legend()
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved {out_path.name}")


def make_funding_bar_chart(summary: pd.DataFrame, dim_label: str, out_path: Path) -> None:
    """Same as above but for total_funding (in $M)."""
    summary = summary.copy()
    summary["total_funding_M"] = summary["total_funding"] / 1e6
    fig, ax = plt.subplots(figsize=(12, 6))
    run_labels = summary["run_label"].unique()
    codes = (
        summary.groupby("code")["total_funding_M"]
        .sum()
        .sort_values(ascending=False)
        .index
    )
    x = range(len(codes))
    width = 0.8 / len(run_labels)
    for i, label in enumerate(run_labels):
        sub = summary[summary["run_label"] == label].set_index("code")
        vals = [sub.loc[c, "total_funding_M"] if c in sub.index else 0 for c in codes]
        ax.bar([xi + i * width for xi in x], vals, width=width, label=label)
    ax.set_xticks([xi + width * (len(run_labels) - 1) / 2 for xi in x])
    ax.set_xticklabels(codes, rotation=45, ha="right")
    ax.set_ylabel("Total funding ($M)")
    ax.set_title(f"{dim_label} distribution — NCI pilot (total funding)")
    ax.legend()
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved {out_path.name}")


def make_time_series_chart(ts: pd.DataFrame, dim_label: str, out_path: Path) -> None:
    """Line chart: n_grants by FY, one line per (run_label × top codes)."""
    # Show top-8 codes by total grant count
    top_codes = ts.groupby("code")["n_grants"].sum().nlargest(8).index
    ts_top = ts[ts["code"].isin(top_codes)].copy()
    ts_top["fy"] = ts_top["fy"].astype(int)
    fig, ax = plt.subplots(figsize=(14, 6))
    for (run_label, code), grp in ts_top.groupby(["run_label", "code"]):
        grp_sorted = grp.sort_values("fy")
        ax.plot(grp_sorted["fy"], grp_sorted["n_grants"],
                label=f"{run_label} / {code}", marker="o", markersize=3)
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel("Number of grants")
    ax.set_title(f"{dim_label} over time — NCI pilot (top 8 codes)")
    ax.legend(fontsize=7, ncol=2)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved {out_path.name}")


def render_summary_md(df: pd.DataFrame) -> str:
    """Generate SUMMARY.md content from loaded results."""
    lines = ["# NCI Pilot Analysis — Summary\n"]
    lines.append("*Auto-generated by `analyze.py`. Edit the header section manually.*\n")

    for run_label in sorted(df["run_label"].unique()):
        sub = df[df["run_label"] == run_label]
        valid = sub[sub["valid_json"] == 1.0]
        lines.append(f"\n## {run_label}\n")
        lines.append(f"- Grants: {len(sub):,} total, {len(valid):,} valid JSON\n")
        lines.append(f"- valid_json rate: {len(valid)/len(sub):.1%}\n")
        valid_codes = valid[valid["valid_codes"] == 1.0]
        lines.append(f"- valid_codes rate: {len(valid_codes)/len(valid):.1%}\n")
        lines.append("\n**Dim1 top codes (grants):**\n")
        dim1_counts = valid["dim1"].value_counts().head(10)
        for code, n in dim1_counts.items():
            lines.append(f"  - `{code}`: {n:,} ({100*n/len(valid):.1f}%)\n")

    lines.append("\n## Charts\n")
    for chart in sorted((_HERE / "charts").glob("*.png")):
        lines.append(f"![{chart.stem}](charts/{chart.name})\n")

    return "".join(lines)


def main(make_charts: bool = True) -> None:
    print("Loading results...")
    df = load_results(_RESULTS)
    print(f"  {len(df):,} total rows across {df['run_label'].nunique()} runs")

    if make_charts:
        _CHARTS.mkdir(exist_ok=True)
        for dim_col, dim_label in [
            ("dim1", "Dim1 — Biomarker Use"),
            ("dim2", "Dim2 — Research Design"),
            ("dim3", "Dim3 — Evidence Strength"),
        ]:
            summary = build_dim_summary(df, dim_col)
            make_dim_bar_chart(summary, dim_label,
                               _CHARTS / f"{dim_col}_n_grants.png")
            make_funding_bar_chart(summary, dim_label,
                                   _CHARTS / f"{dim_col}_funding.png")
            ts = build_time_series(df, dim_col)
            make_time_series_chart(ts, dim_label,
                                   _CHARTS / f"{dim_col}_over_time.png")

    summary_text = render_summary_md(df)
    summary_path = _HERE / "SUMMARY.md"
    summary_path.write_text(summary_text)
    print(f"  Wrote {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args()
    main(make_charts=not args.no_charts)
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_nci_pilot_analyze.py -v
```
Expected: All tests PASS.

**Step 5: Run analyze on the real data**

```bash
.venv/bin/python analysis/nci-pilot/analyze.py
ls analysis/nci-pilot/charts/
cat analysis/nci-pilot/SUMMARY.md | head -30
```
Expected: 9 PNG charts in `charts/`, `SUMMARY.md` with counts and chart links.

**Step 6: Commit**

```bash
git add analysis/nci-pilot/analyze.py tests/test_nci_pilot_analyze.py
git add -f analysis/nci-pilot/SUMMARY.md
git commit -m "analysis: add analyze.py — per-grant CSVs → charts and SUMMARY.md"
```

---

## Task 5: Write `analysis/nci-pilot/Makefile`

**Files:**
- Create: `analysis/nci-pilot/Makefile`

**Step 1: Create the Makefile**

```makefile
# analysis/nci-pilot/Makefile
# Run from repo root: make -C analysis/nci-pilot [target]
# Or from this directory: make [target]

PYTHON := ../../.venv/bin/python

.PHONY: extract analyze all clean

all: extract analyze

extract:
	$(PYTHON) extract.py

analyze:
	$(PYTHON) analyze.py

summary:
	$(PYTHON) analyze.py --no-charts

clean:
	rm -f results/*.csv charts/*.png SUMMARY.md
```

**Step 2: Test the Makefile**

```bash
# From repo root:
make -C analysis/nci-pilot summary
```
Expected: Runs `analyze.py --no-charts`, updates `SUMMARY.md`.

**Step 3: Commit**

```bash
git add analysis/nci-pilot/Makefile
git commit -m "analysis: add Makefile for nci-pilot (extract, analyze, summary targets)"
```

---

## Task 6: Write user-level rubric design skill

**Purpose:** A durable methodological skill encoding psychometric and scientific principles for rubric/classification taxonomy design. Lives at user level so it applies across all projects (this repo, fleet-ds-gym, any future rubric work).

**File:**
- Create: `~/.claude/skills/rubric-design/SKILL.md`
- Modify: `~/.claude/MEMORY.md` (add pointer)

**Step 1: Read the fleet-ds-gym build-rubric skill for content to consolidate**

```bash
cat /Users/mnarayan/Documents/Coding/Cloud/fleet-ds-gym/.claude/skills/build-rubric/SKILL.md
```

Key content to inherit:
- Model capability vs. instrument validity distinction
- Rubric as hypothesis, not spec
- After-first-run evaluation cycle (review criteria that all fail, all pass, discriminate poorly)
- Targeted validation techniques (positive/negative controls, discriminative validity)

**Step 2: Create `~/.claude/skills/rubric-design/SKILL.md`**

```markdown
---
name: rubric-design
description: Use when designing, evaluating, or iterating on a classification rubric or measurement instrument for LLM grading tasks — covers validity, reliability, calibration, and iteration protocol using psychometric principles
---

# Rubric Design — Scientific Principles

This skill encodes the scientific methodology for rubric design. It applies whenever you are creating or revising a classification taxonomy, grading rubric, or evaluation instrument used to assess LLM outputs or human judgments.

The core principle: **a rubric is a measurement instrument, not a specification.** It makes empirical claims about a construct (what it measures, how it categorises, where boundaries lie). Those claims must be tested, not just implemented.

## Invoke alongside

Always invoke `/edit-scientific-docs` when editing rubric content — the domain expert owns the scientific claims; your role is structural.

## Taxonomy Design: What Makes a Valid Classification Instrument

Before running any model, the taxonomy itself must satisfy:

**Exhaustiveness:** Every real case in the domain must map to exactly one code. Gaps force the model to pick the nearest code, producing systematic mislabelling. Signs of a gap: high frequency of one "catch-all" code, unexpected clustering, inter-model disagreement on a specific case type.

**Mutual exclusivity:** Codes at the same level must not overlap in definition. Overlapping codes produce unreliable assignments — different judges (human or model) resolve ambiguity differently. Signs of overlap: high inter-model disagreement on the same cases, model assigns both codes depending on wording.

**Construct specificity:** Each code must refer to a single, specific concept. Composite codes (e.g. "diagnostic or prognostic") conflate distinct constructs and make level-1 partial credit meaningless.

**Explicit rejection paths:** Any case that does not belong in the scored taxonomy must have an explicit code (`not_applicable`, `out_of_scope`, etc.). Without explicit rejection, models default to the closest-sounding valid code rather than rejecting. Every non-target case type needs its own named branch.

## Validity

**Construct validity:** Does the taxonomy measure what it claims? Ask: if a domain expert read only the code definitions, could they assign cases reliably without further instruction? If definitions require domain background knowledge not in the rubric, construct validity is compromised.

**Content validity:** Are all substantively distinct cases covered? Content gaps are discovered by reviewing misclassifications — cases where the model's assignment is understandable but wrong because no better code exists.

**Discriminant validity:** Can the rubric distinguish categories that should be distinct? Test by examining cases near code boundaries. If two codes are consistently confused, either the definitions overlap or the boundary is genuinely ambiguous (a domain question, not a rubric question).

## Reliability

**Inter-rater reliability (inter-model agreement):** Measures consistency across independent judges applying the same rubric. Low agreement signals rubric underspecification — the rubric does not constrain the assignment enough. High agreement on wrong answers signals a shared systematic bias (e.g. both models under-read a code definition the same way).

**Test-retest stability:** Same model, same rubric, different runs. High variability signals temperature sensitivity or prompt instability, not rubric issues. Run temperature=0 to separate rubric instability from stochastic variation.

**Wording sensitivity:** Small rubric edits should not cause large distribution shifts. If adding one sentence shifts 10% of assignments, the rubric boundary was previously underspecified for that region.

## Calibration

A calibration set is a small collection of cases with known correct labels (ground truth established by domain expert, not model output). Its purpose:

- **Anchor the instrument:** Prevents rubric drift across iterations — if calibration accuracy drops, the rubric changed what it measures.
- **Expose underspecification:** Calibration failures reveal where the rubric does not constrain assignment to the correct code.
- **Not a benchmark:** Calibration cases are not a random sample; they deliberately cover boundary cases, known ambiguities, and typical examples. Do not generalise calibration accuracy to full-population accuracy.

Ground truth for calibration cases must come from the domain expert, not from model output or agent reasoning.

## Rubric as Hypothesis: The Iteration Protocol

A rubric's first deployment is a validity test, not a production run.

After each run, examine:

1. **Distribution plausibility:** Do the code frequencies make sense given what you know about the domain? Unexpected concentrations signal a gap or a dominant code absorbing cases that should go elsewhere.

2. **Calibration accuracy:** Do gold-labeled examples score correctly? Failures identify specific definition gaps or ambiguities to fix.

3. **Inter-model disagreement structure:** Where do models diverge? Systematic disagreement on a code type signals rubric underspecification for that type, not random error. Use a tiebreaker (stronger model, human review) to determine which model is correct.

4. **All-fail / all-pass criteria:** A code that never appears may be correctly absent (rare phenomenon) or inaccessible (definition is too narrow or overlaps with another code). A code that appears on nearly everything may be a catch-all absorbing cases that belong elsewhere.

## Model Capability vs. Instrument Validity

These are independent questions. A model failing to assign a code correctly can reflect:
- *Rubric underspecification:* The definition doesn't constrain the assignment (rubric problem)
- *Model capability:* The model lacks the domain knowledge to apply the rubric correctly (model problem)
- *Construct ambiguity:* The distinction the rubric tries to make is genuinely hard even for domain experts (domain problem)

Do not weaken rubric criteria because models fail them. Diagnose first. Use a stronger model or human review as a tiebreaker before concluding the rubric needs revision.

## What Instability Looks Like

| Signal | Likely cause |
|--------|-------------|
| Inter-model disagreement clustered on specific codes | Rubric underspecification for those codes |
| High rate of one rejection code | Missing code for a substantive case type |
| Large distribution shift after minor rubric edit | Previous definition was ambiguous; edit resolved the ambiguity |
| Model assigns "closest" code to cases that should be rejected | Missing explicit rejection branch |
| Calibration failure on boundary cases only | Boundary definitions need sharpening |
| Calibration failure across many cases after rubric edit | Edit changed the meaning of a code unexpectedly |

## Targeted Validation (Optional, When Warranted)

These are not routine — use them when the iteration cycle raises a specific concern:

- **Positive control:** Add a hint to the prompt that should make a criterion easy. If the model still fails, the issue is model capability, not rubric specification.
- **Negative control:** Verify that a known-incorrect submission loses points on the relevant criterion. If it doesn't, the criterion lacks discriminative power.
- **Discriminative validity check:** Compare assignments on cases that clearly do vs. clearly don't exhibit the target concept. If both score the same, the criterion cannot differentiate them.
```

**Step 3: Update `~/.claude/MEMORY.md`**

Add a line under the appropriate section:
```markdown
- [rubric-design skill](~/.claude/skills/rubric-design/SKILL.md) — psychometric principles for rubric/classification taxonomy design; invoke for any rubric work across projects
```

**Step 4: Commit (skills live outside the repo — no git commit needed)**

Verify the file exists:
```bash
cat ~/.claude/skills/rubric-design/SKILL.md | head -10
```

---

## Task 7: Write project-level rubric skill

**Purpose:** A thin project-specific skill that explains which components of `rubric-design` apply at this project's current stage, names the known instabilities discovered in this project, and defines the testing loop.

**File:**
- Create: `.claude/skills/rubric/SKILL.md`

**Step 1: Create `.claude/skills/` directory**

```bash
mkdir -p .claude/skills/rubric
```

**Step 2: Create `.claude/skills/rubric/SKILL.md`**

```markdown
---
name: rubric
description: Use when editing, testing, or iterating on data/RUBRIC.md in this project — covers which validity checks apply now, the testing loop, and known instabilities discovered in this project's grading runs
---

# NIH Biomarker Funding — Rubric Skill

## Required companion skill

Always invoke `/rubric-design` (user-level) before working on this rubric. It contains the psychometric methodology that governs all decisions here. This skill explains how to apply it to this project specifically.

Also invoke `/edit-scientific-docs` when editing RUBRIC.md content — Manjari owns all scientific claims.

## What this rubric is

`data/RUBRIC.md` is a three-dimensional classification taxonomy for NIH grants:
- **Dim1** — Biomarker use type (21 codes, including 2 rejection codes)
- **Dim2** — Research design (10 codes; null when Dim1 is a rejection code)
- **Dim3** — Evidence strength (5 codes; null when Dim1 is a rejection code)

Codes are **parsed from RUBRIC.md at import time** by `inspect_task.parse_rubric_codes()` — adding or removing a `**\`code\`**` entry in RUBRIC.md auto-propagates to the enum sets used by the scorer and tests. No hardcoded changes needed elsewhere.

The grading pipeline: `data/RUBRIC.md` → `scripts/grader_prompt.py:build_system_prompt()` → `inspect_task.py` → Inspect AI eval → `.eval` logs → `analysis/nci-pilot/`.

## Which validity checks apply now (current stage: basic)

We are not yet doing full psychometric validation. The current tier:

1. **Calibration accuracy** — run `inspect eval` on `data/grader_calibration_examples.csv` (48 rows with `GOLD_DIM1` labels) and check that gold-labeled examples score the correct Dim1 code. This is the minimum gate before any full production run.

2. **Inter-model agreement** — compare Gemini 2.5 Flash Lite vs. GPT-OSS-120B assignments on the same grants. Disagreement clusters identify underspecified codes. See `analysis/nci-pilot/` for the current comparison.

3. **Distribution plausibility** — after any full run, check Dim1 frequencies against domain expectations. Unexpectedly high rejection rates or unexpected clustering warrant investigation before treating results as valid.

Not yet in scope: full discriminant validity, IRT, prompt sensitivity A/B tests.

## Testing loop (before committing any RUBRIC.md change)

```bash
# 1. Run calibration set (25-grant limit for speed)
INSPECT=.venv/bin/inspect
$INSPECT eval inspect_task.py \
  --model google/gemini-2.5-flash-lite \
  --temperature 0.0 \
  --limit 48 \
  -T dataset_path=data/grader_calibration_examples.csv \
  --log-dir logs/test-rubric-calibration/

# 2. Check gold label accuracy
python scripts/analyze_eval_results.py logs/test-rubric-calibration/

# 3. Review any GOLD_DIM1 mismatches before committing the rubric change
# If calibration fails → diagnose (rubric underspecification vs. model failure) → fix → repeat
# If calibration passes → commit rubric change → append row to logs/manifest.csv
```

## Known instabilities and their causes

These were discovered in real grading runs (NCI sample, April 2026). Do not revisit these as design questions without new evidence — they are settled decisions:

**not_applicable vs. disease_non_biomarker (resolved):** The original rubric had only `not_applicable` as a rejection code. Haiku tiebreaker analysis on 30 inter-model disagreements found that Gemini was assigning biomarker codes (`susceptibility_risk`, `pharmacodynamic`, `stratification_diagnostic`) to grants conducting disease biology or treatment research that mentioned a molecule with biomarker relevance in other contexts. Root cause: no rejection code existed for substantive disease research without a biomarker component. Resolution: `disease_non_biomarker` added as a second rejection code; Step 0 updated to three branches (infrastructure → `not_applicable`; disease research without biomarker component → `disease_non_biomarker`; biomarker research → continue).

**"Primary or significant component" threshold:** The boundary between `disease_non_biomarker` and a valid biomarker code required two rounds of correction. The correct threshold: biomarker use is a primary or significant component when the grant uses biomarkers to investigate disease processes, discovers biomarker or assay technologies, or applies a biomarker in any defined context of use — in any direction, not limited to specific therapeutic or regulatory strategies.

**Gemini over-assignment pattern:** As of the April 2026 runs, Gemini 2.5 Flash Lite under-assigns `not_applicable` and `disease_non_biomarker` relative to GPT-OSS-120B. Haiku judged GPT correct in 24/30 disagreement cases. This pattern should be monitored in future runs to assess whether rubric changes (disease_non_biomarker addition) reduce the gap.

## When to escalate to Manjari

These decisions require her judgment — do not resolve them yourself:

- Any new rejection code or new Dim1 code
- Changes to the "primary or significant component" threshold
- Any change to Dim2 or Dim3 code definitions
- Interpreting whether inter-model disagreement reflects rubric underspecification or genuine construct ambiguity
- Deciding whether a failing calibration case reflects a rubric problem or a model capability problem
```

**Step 3: Verify skill is in place**

```bash
cat .claude/skills/rubric/SKILL.md | head -10
```

**Step 4: Commit**

```bash
git add .claude/skills/rubric/SKILL.md
git commit -m "docs: add project-level rubric skill — testing loop, known instabilities, validity tier"
```

---

## Verification Checklist

Before considering this plan complete, verify:

- [ ] `bash scripts/run-grading.sh --model google/gemini-2.5-flash-lite` from worktree does not print "No such file or directory"
- [ ] `make -C analysis/nci-pilot extract` produces two CSVs in `results/`, ~3,770 rows each
- [ ] `make -C analysis/nci-pilot analyze` produces 9 charts and `SUMMARY.md`
- [ ] `.venv/bin/python -m pytest tests/test_nci_pilot_extract.py tests/test_nci_pilot_analyze.py -v` — all tests pass
- [ ] `cat ~/.claude/skills/rubric-design/SKILL.md | head -5` shows the skill header
- [ ] `cat .claude/skills/rubric/SKILL.md | head -5` shows the project skill header
