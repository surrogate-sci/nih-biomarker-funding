# Biomarker Screening Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a self-contained descriptive analysis of the ~270K keyword-filtered NIH biomarker grant dataset, characterizing the research universe before LLM grading.

**Architecture:** A self-contained `analysis/biomarker-screening/` directory with a Python analysis script, utility module, generated charts, and a narrative SUMMARY.md. Data is read from `data/nih_biomarker_unified_2004-2024.csv` (124MB, 269,630 grants). Charting uses **Datawrapper** (primary, publication-quality) with **seaborn/matplotlib** fallback when no API token is set. The analysis script auto-detects `DATAWRAPPER_API_TOKEN` at runtime and chooses the renderer.

**Tech Stack:** Python 3.11, pandas, datawrapper, seaborn, matplotlib

---

## Context

We have a crude keyword-filtered dataset of ~270K NIH grants (FY2004-2024, $134.49B). This is NOT the full landscape analysis — it's the screening step. Before any LLM grading refines classification, we need to understand what this keyword filter captured: how big is it, how has it grown, who funds it, what kinds of grants.

From `docs/session-notes/2026-03-19-dataset-release-and-access.md`, the analysis goals are:
1. Define the biomarker research universe — core (4) vs expanded (10) terms, data quality gaps
2. Funding summaries — total, by institute, by year
3. Grant mechanism breakdown — R01 vs clinical trial types
4. Explicit biomarker term adoption over time

## CLAUDE.md Update

Add a Visualization section to CLAUDE.md Rules:

```
- **Visualization**: For analysis outputs and publication-quality charts, use Python data science
  libraries (seaborn, matplotlib, plotnine, bokeh) or Datawrapper. Chart.js is acceptable only
  for quick dev prototyping during iteration. Target: Datawrapper for final blog-ready figures.
```

## File Structure

```
analysis/biomarker-screening/
├── requirements.txt              # pandas, datawrapper, seaborn, matplotlib
├── utils.py                      # Data loading, cleaning, FY annotation helpers
├── charts.py                     # Charting abstraction: Datawrapper (primary) or seaborn (fallback)
├── analyze.py                    # Main analysis: computes all stats, calls charts.py
├── charts/                       # Generated outputs (PNG or Datawrapper URLs + funding_analysis.json)
├── test_utils.py                 # Tests for data loading
└── SUMMARY.md                    # Narrative summary of findings (generated + hand-edited)

CLAUDE.md                         # Add visualization rule
```

**Key design decisions:**
- **Datawrapper first**: `charts.py` checks for `DATAWRAPPER_API_TOKEN` env var. If present, creates charts via Datawrapper API (publication-quality, embeddable). If absent, falls back to seaborn/matplotlib PNG. Both paths produce the same structured JSON output.
- Single `analyze.py` script (not a notebook) — jupyter isn't installed, and a .py is easier to run headless and commit. Can convert to notebook later.
- `charts.py` separates charting logic from analysis logic — swapping renderers is one-file change
- `funding_analysis.json` as structured output regardless of renderer
- `utils.py` keeps data loading DRY if we add more analyses later

**Datawrapper setup** (for when Manjari has a token):
1. Create free account at app.datawrapper.de
2. Generate API token at app.datawrapper.de/account/api-tokens (scope: `chart:write`, `chart:read`)
3. Set `export DATAWRAPPER_API_TOKEN=<token>` or add to `.env`
4. Re-run `python analyze.py` — charts auto-upgrade to Datawrapper

## Dataset Reference

**File:** `data/nih_biomarker_unified_2004-2024.csv` (269,746 rows including header)

**Columns used in this analysis:**
| Column | Use |
|--------|-----|
| `FY` | Fiscal year (2004-2024) |
| `TOTAL_COST` | Grant funding amount |
| `ADMINISTERING_IC` | Institute code (e.g., CA=NCI) |
| `IC_NAME` | Institute name |
| `ACTIVITY` | Grant mechanism (R01, R21, U01, etc.) |
| `FUNDING_MECHANISM` | Mechanism category |
| `EXPLICIT_BIOMARKER` | TRUE if matched core 4 terms |
| `APPLICATION_ID` | Unique grant ID |

**Known data quality issues:**
- FY2005: PROJECT_TERMS 68% populated → undercount
- FY2006: PROJECT_TERMS completely empty → severe undercount
- These years should be annotated on all time-series charts

**Validation targets** (from `data/filtered/SUMMARY.md`):
- Total grants: 269,630
- Explicit biomarker grants: 75,849
- Total spending: $134.49B
- Explicit biomarker spending: $35.77B

---

### Task 0: Environment Setup

**Files:**
- Create: `analysis/biomarker-screening/requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p analysis/biomarker-screening/charts
```

- [ ] **Step 2: Create requirements.txt**

```
pandas>=2.0
datawrapper>=2.0
seaborn>=0.13
matplotlib>=3.8
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r analysis/biomarker-screening/requirements.txt
```

Expected: Successfully installed pandas, seaborn, matplotlib

- [ ] **Step 4: Verify dataset exists**

```bash
wc -l data/nih_biomarker_unified_2004-2024.csv
```

Expected: `269747` (269,746 data rows + 1 header)

- [ ] **Step 5: Commit**

```bash
git add analysis/biomarker-screening/requirements.txt
git commit -m "analysis: scaffold biomarker-screening directory"
```

---

### Task 1: Data Loading Utilities

**Files:**
- Create: `analysis/biomarker-screening/utils.py`
- Create: `analysis/biomarker-screening/test_utils.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for biomarker screening analysis utilities."""
import unittest
from pathlib import Path


class TestLoadDataset(unittest.TestCase):
    def test_load_returns_dataframe_with_expected_columns(self):
        from utils import load_dataset

        df = load_dataset()
        for col in ["FY", "TOTAL_COST", "ADMINISTERING_IC", "EXPLICIT_BIOMARKER", "ACTIVITY"]:
            self.assertIn(col, df.columns)

    def test_load_has_expected_row_count(self):
        from utils import load_dataset

        df = load_dataset()
        # Should be ~269,630 rows (allow small tolerance for dedup differences)
        self.assertGreater(len(df), 260_000)
        self.assertLess(len(df), 280_000)

    def test_explicit_biomarker_is_boolean(self):
        from utils import load_dataset

        df = load_dataset()
        self.assertTrue(df["EXPLICIT_BIOMARKER"].dtype == bool)

    def test_total_cost_is_numeric(self):
        from utils import load_dataset

        df = load_dataset()
        self.assertTrue(df["TOTAL_COST"].dtype in ["float64", "int64"])


class TestDataQualityYears(unittest.TestCase):
    def test_data_quality_years_constant(self):
        from utils import DATA_QUALITY_YEARS

        self.assertIn(2005, DATA_QUALITY_YEARS)
        self.assertIn(2006, DATA_QUALITY_YEARS)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd analysis/biomarker-screening && python -m pytest test_utils.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'utils'`

- [ ] **Step 3: Write utils.py**

```python
"""Utilities for biomarker screening analysis.

Loads and cleans the unified NIH biomarker dataset.
"""
from pathlib import Path

import pandas as pd

# Project root: analysis/biomarker-screening/../../
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "nih_biomarker_unified_2004-2024.csv"

# Years with known PROJECT_TERMS data quality issues
DATA_QUALITY_YEARS = {2005, 2006}


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Load the unified biomarker dataset with type cleaning.

    Returns DataFrame with:
    - EXPLICIT_BIOMARKER as bool
    - TOTAL_COST as float (NaN for missing)
    - FY as int
    """
    df = pd.read_csv(
        path,
        dtype={"APPLICATION_ID": str, "ADMINISTERING_IC": str, "ACTIVITY": str},
        low_memory=False,
    )
    df["EXPLICIT_BIOMARKER"] = df["EXPLICIT_BIOMARKER"].fillna(False).astype(bool)
    df["TOTAL_COST"] = pd.to_numeric(df["TOTAL_COST"], errors="coerce")
    df["FY"] = df["FY"].astype(int)
    return df


def activity_category(activity: str) -> str:
    """Map NIH activity codes to broad categories.

    R-series: Research grants (R01, R21, R03, R15, R33, R34, R35, R37, R41, R42, R43, R44, etc.)
    P-series: Program/center grants (P01, P20, P30, P50, etc.)
    U-series: Cooperative agreements (U01, U10, U19, U24, U54, etc.)
    K-series: Career development (K01, K08, K23, K25, K99, etc.)
    T/F-series: Training/fellowship (T32, F30, F31, F32, etc.)
    Other: Contracts, intramural, misc
    """
    if not isinstance(activity, str) or len(activity) < 1:
        return "Other"
    prefix = activity[0].upper()
    category_map = {"R": "Research (R)", "P": "Program/Center (P)", "U": "Cooperative (U)",
                    "K": "Career Dev (K)", "T": "Training (T)", "F": "Fellowship (F)"}
    return category_map.get(prefix, "Other")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd analysis/biomarker-screening && python -m pytest test_utils.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add analysis/biomarker-screening/utils.py analysis/biomarker-screening/test_utils.py
git commit -m "analysis: add data loading utilities with tests"
```

---

### Task 2: Charting Abstraction (Datawrapper + seaborn fallback)

**Files:**
- Create: `analysis/biomarker-screening/charts.py`

This module provides a simple charting API. If `DATAWRAPPER_API_TOKEN` is set, it creates charts via the Datawrapper API (publication-quality, embeddable). Otherwise, it falls back to seaborn/matplotlib PNGs.

- [ ] **Step 1: Write charts.py**

```python
"""Charting abstraction: Datawrapper (primary) or seaborn/matplotlib (fallback).

Usage:
    from charts import get_renderer
    renderer = get_renderer(output_dir)
    renderer.stacked_area(df, x="FY", y_cols=["explicit", "expanded"], ...)
    renderer.horizontal_bar(df, x="funding", y="institute", ...)
    renderer.line(df, x="FY", y="pct", ...)
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE = sns.color_palette("colorblind")


def _billions(x, _pos=None):
    return f"${x / 1e9:.1f}B"


def get_renderer(output_dir: Path) -> "ChartRenderer":
    """Return Datawrapper renderer if token is set, else seaborn fallback."""
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if token:
        return DatawrapperRenderer(output_dir, token)
    print("  [charts] No DATAWRAPPER_API_TOKEN — using seaborn/matplotlib fallback")
    return SeabornRenderer(output_dir)


class SeabornRenderer:
    """Fallback renderer using seaborn/matplotlib → PNG files."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "seaborn"

    def stacked_area(self, df: pd.DataFrame, x: str, y_cols: list[str],
                     labels: list[str], title: str, filename: str,
                     ylabel: str = "Total Funding", vlines: list[int] | None = None):
        fig, ax = plt.subplots(figsize=(12, 6))
        bottom = pd.Series(0.0, index=df.index)
        for col, label, color in zip(y_cols, labels, PALETTE):
            ax.fill_between(df[x], bottom, bottom + df[col], alpha=0.7,
                            label=label, color=color)
            bottom = bottom + df[col]

        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(loc="upper left")

        if vlines:
            for yr in vlines:
                ax.axvline(x=yr, color="red", linestyle="--", alpha=0.4)
                ax.annotate("data gap", xy=(yr, ax.get_ylim()[1] * 0.95),
                            fontsize=8, color="red", ha="center")

        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def horizontal_bar(self, df: pd.DataFrame, x: str, y: str,
                       title: str, filename: str, annotations: str | None = None):
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.barplot(data=df, y=y, x=x, ax=ax, palette="viridis")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Total Funding")
        ax.set_ylabel("")
        ax.set_title(title)

        if annotations:
            for i, row in enumerate(df.itertuples()):
                val = getattr(row, annotations)
                ax.text(getattr(row, x), i, f"  {val:,} grants",
                        va="center", fontsize=8)

        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def area_by_category(self, pivot: pd.DataFrame, title: str, filename: str):
        fig, ax = plt.subplots(figsize=(12, 6))
        pivot.plot.area(ax=ax, alpha=0.7)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_billions))
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel("Total Funding")
        ax.set_title(title)
        ax.legend(title="Mechanism", bbox_to_anchor=(1.05, 1), loc="upper left")
        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)

    def line(self, df: pd.DataFrame, x: str, y: str,
             title: str, filename: str, ylabel: str = "",
             ylim: tuple | None = None, vlines: list[int] | None = None):
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df[x], df[y], marker="o", color=PALETTE[2], linewidth=2)
        ax.set_xlabel("Fiscal Year")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        if ylim:
            ax.set_ylim(*ylim)
        if vlines:
            for yr in vlines:
                ax.axvline(x=yr, color="red", linestyle="--", alpha=0.4)
        fig.tight_layout()
        path = self.output_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"  Saved {path}")
        return str(path)


class DatawrapperRenderer:
    """Primary renderer using Datawrapper API → published charts."""

    def __init__(self, output_dir: Path, token: str):
        from datawrapper import Datawrapper
        self.dw = Datawrapper(access_token=token)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.backend = "datawrapper"
        self.chart_urls: dict[str, str] = {}

    def _create_and_publish(self, chart_type: str, title: str, data: pd.DataFrame,
                            filename: str, metadata: dict | None = None) -> str:
        chart_info = self.dw.create_chart(title=title, chart_type=chart_type)
        chart_id = chart_info["id"]
        self.dw.add_data(chart_id, data)
        if metadata:
            self.dw.update_metadata(chart_id, metadata)
        self.dw.publish_chart(chart_id)
        url = f"https://datawrapper.dwcdn.net/{chart_id}/"
        self.chart_urls[filename] = url

        # Save URL reference locally
        ref_path = self.output_dir / f"{filename}.url"
        ref_path.write_text(url)
        print(f"  Published: {url}")
        return url

    def stacked_area(self, df: pd.DataFrame, x: str, y_cols: list[str],
                     labels: list[str], title: str, filename: str, **kwargs):
        chart_df = df[[x] + y_cols].copy()
        chart_df.columns = [x] + labels
        return self._create_and_publish("d3-area", title, chart_df, filename)

    def horizontal_bar(self, df: pd.DataFrame, x: str, y: str,
                       title: str, filename: str, **kwargs):
        chart_df = df[[y, x]].copy()
        return self._create_and_publish("d3-bars", title, chart_df, filename)

    def area_by_category(self, pivot: pd.DataFrame, title: str, filename: str):
        chart_df = pivot.reset_index()
        return self._create_and_publish("d3-area", title, chart_df, filename)

    def line(self, df: pd.DataFrame, x: str, y: str,
             title: str, filename: str, **kwargs):
        chart_df = df[[x, y]].copy()
        return self._create_and_publish("d3-lines", title, chart_df, filename)
```

- [ ] **Step 2: Commit**

```bash
git add analysis/biomarker-screening/charts.py
git commit -m "analysis: add charting abstraction (datawrapper primary, seaborn fallback)"
```

---

### Task 3: Core Analysis Script

**Files:**
- Create: `analysis/biomarker-screening/analyze.py`

- [ ] **Step 1: Write analyze.py using charts.py abstraction**

```python
#!/usr/bin/env python3
"""Biomarker Screening Analysis — descriptive statistics and charts.

Reads the unified NIH biomarker dataset and produces:
- Funding over time (total vs explicit biomarker)
- Top institutes by funding
- Grant mechanism breakdown
- Explicit biomarker adoption rate

Uses Datawrapper if DATAWRAPPER_API_TOKEN is set, else seaborn/matplotlib.
Outputs: charts/ directory + funding_analysis.json
"""
import json
from pathlib import Path

import pandas as pd

from charts import get_renderer
from utils import load_dataset, activity_category, DATA_QUALITY_YEARS

CHARTS_DIR = Path(__file__).parent / "charts"


def funding_over_time(df: pd.DataFrame, renderer) -> dict:
    """Compute and plot funding over time."""
    yearly = df.groupby("FY").agg(
        total_funding=("TOTAL_COST", "sum"),
        grant_count=("APPLICATION_ID", "count"),
    ).reset_index()

    explicit_yearly = df[df["EXPLICIT_BIOMARKER"]].groupby("FY")["TOTAL_COST"].sum()
    yearly["explicit_funding"] = yearly["FY"].map(explicit_yearly).fillna(0)
    yearly["expanded_only_funding"] = yearly["total_funding"] - yearly["explicit_funding"]

    renderer.stacked_area(
        yearly, x="FY",
        y_cols=["explicit_funding", "expanded_only_funding"],
        labels=["Core terms (4)", "Expanded terms only (+6)"],
        title="NIH Biomarker-Related Funding by Keyword Match Type (FY2004–2024)",
        filename="funding_over_time.png",
        vlines=sorted(DATA_QUALITY_YEARS),
    )

    return {
        "years": yearly["FY"].tolist(),
        "total_funding": yearly["total_funding"].tolist(),
        "explicit_funding": yearly["explicit_funding"].tolist(),
        "grant_count": yearly["grant_count"].tolist(),
    }


def top_institutes(df: pd.DataFrame, renderer, n: int = 15) -> dict:
    """Compute and plot top institutes by funding."""
    ic = df.groupby(["ADMINISTERING_IC", "IC_NAME"]).agg(
        total_funding=("TOTAL_COST", "sum"),
        grant_count=("APPLICATION_ID", "count"),
    ).reset_index().sort_values("total_funding", ascending=False).head(n)

    renderer.horizontal_bar(
        ic, x="total_funding", y="ADMINISTERING_IC",
        title=f"Top {n} NIH Institutes by Biomarker-Related Funding",
        filename="top_institutes.png",
        annotations="grant_count",
    )

    return {
        "institutes": ic[["ADMINISTERING_IC", "IC_NAME", "total_funding", "grant_count"]]
        .to_dict(orient="records")
    }


def mechanism_breakdown(df: pd.DataFrame, renderer) -> dict:
    """Compute and plot grant mechanism breakdown over time."""
    df = df.copy()
    df["category"] = df["ACTIVITY"].apply(activity_category)

    cat_year = df.groupby(["FY", "category"]).agg(
        total_funding=("TOTAL_COST", "sum"),
    ).reset_index()

    pivot = cat_year.pivot_table(index="FY", columns="category",
                                  values="total_funding", fill_value=0)

    renderer.area_by_category(
        pivot,
        title="Biomarker Funding by Grant Mechanism Category (FY2004–2024)",
        filename="mechanism_breakdown.png",
    )

    overall = df.groupby("category").agg(
        total_funding=("TOTAL_COST", "sum"),
        grant_count=("APPLICATION_ID", "count"),
    ).sort_values("total_funding", ascending=False).reset_index()

    return {"categories": overall.to_dict(orient="records")}


def explicit_adoption(df: pd.DataFrame, renderer) -> dict:
    """Plot explicit biomarker term adoption rate over time."""
    yearly = df.groupby("FY").agg(
        total=("APPLICATION_ID", "count"),
        explicit=("EXPLICIT_BIOMARKER", "sum"),
    ).reset_index()
    yearly["pct_explicit"] = 100.0 * yearly["explicit"] / yearly["total"]

    renderer.line(
        yearly, x="FY", y="pct_explicit",
        title="Adoption of Explicit 'Biomarker' Terminology in NIH Grants",
        filename="explicit_adoption.png",
        ylabel="% Grants Using Core Biomarker Terms",
        ylim=(0, 100),
        vlines=sorted(DATA_QUALITY_YEARS),
    )

    return {
        "years": yearly["FY"].tolist(),
        "pct_explicit": yearly["pct_explicit"].round(1).tolist(),
    }


def main():
    print("Loading dataset...")
    df = load_dataset()
    print(f"  {len(df):,} grants loaded")

    assert abs(len(df) - 269_630) < 200, f"Unexpected row count: {len(df)}"
    total_b = df["TOTAL_COST"].sum()
    print(f"  Total funding: ${total_b/1e9:.2f}B")

    renderer = get_renderer(CHARTS_DIR)
    print(f"  Using {renderer.backend} renderer\n")

    results = {}
    print("1. Funding over time...")
    results["funding_over_time"] = funding_over_time(df, renderer)

    print("\n2. Top institutes...")
    results["top_institutes"] = top_institutes(df, renderer)

    print("\n3. Grant mechanism breakdown...")
    results["mechanism_breakdown"] = mechanism_breakdown(df, renderer)

    print("\n4. Explicit biomarker adoption...")
    results["explicit_adoption"] = explicit_adoption(df, renderer)

    results["summary"] = {
        "total_grants": len(df),
        "explicit_grants": int(df["EXPLICIT_BIOMARKER"].sum()),
        "total_funding_billions": round(df["TOTAL_COST"].sum() / 1e9, 2),
        "explicit_funding_billions": round(
            df[df["EXPLICIT_BIOMARKER"]]["TOTAL_COST"].sum() / 1e9, 2
        ),
        "year_range": [int(df["FY"].min()), int(df["FY"].max())],
        "data_quality_years": sorted(DATA_QUALITY_YEARS),
        "renderer": renderer.backend,
    }

    out_path = CHARTS_DIR / "funding_analysis.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the analysis**

```bash
cd analysis/biomarker-screening && python analyze.py
```

Expected (without token):
```
Loading dataset...
  269,630 grants loaded
  Total funding: $134.49B
  [charts] No DATAWRAPPER_API_TOKEN — using seaborn/matplotlib fallback
  Using seaborn renderer

1. Funding over time...
  Saved charts/funding_over_time.png
...
```

- [ ] **Step 3: Verify charts exist**

```bash
ls -la analysis/biomarker-screening/charts/
```

Expected: 4 PNG files + 1 JSON file

- [ ] **Step 4: Commit**

```bash
git add analysis/biomarker-screening/analyze.py
git commit -m "analysis: add biomarker screening analysis script with 4 chart types"
```

---

### Task 4: Narrative Summary

**Files:**
- Create: `analysis/biomarker-screening/SUMMARY.md`

- [ ] **Step 1: Write SUMMARY.md template**

Write the initial structure. Exact numbers will be filled in from `funding_analysis.json` output after running `analyze.py`:

```markdown
# Biomarker Screening: Dataset Characterization

## What This Is

A keyword-filtered subset of all NIH-funded grants from FY2004–2024. This is a **screening
step**, not a classification — it identifies grants that *mention* biomarker-related concepts
in their title or project terms, without judging how they use those concepts.

### Methodology

**Core terms (4):** biomarker, clinical marker, surrogate endpoint, imaging marker
**Expanded terms (+6):** digital biomarker, intermediate outcome, endophenotype, genetic marker,
clinical+omics, clinical+imaging

Grants matching core terms are flagged `EXPLICIT_BIOMARKER=TRUE`. All others matched via
expanded terms only. Matching is case-insensitive against PROJECT_TITLE and PROJECT_TERMS
fields in NIH ExPORTER data.

### Data Quality Caveats

- **FY2005**: PROJECT_TERMS field only 68% populated → undercounts expanded-term matches
- **FY2006**: PROJECT_TERMS field completely empty → severe undercount
- These years are annotated on all time-series charts

## Key Numbers

- **Total grants:** [from analysis]
- **Total funding:** [from analysis]
- **Explicit biomarker grants:** [from analysis] ([pct]%)
- **Explicit biomarker funding:** [from analysis] ([pct]%)
- **Year range:** FY2004–2024

## Findings

### 1. Funding Has Grown ~8x in 20 Years

[Chart: funding_over_time.png]

[Narrative from data]

### 2. NCI Dominates Biomarker Funding

[Chart: top_institutes.png]

[Narrative from data]

### 3. R01 Grants Are the Primary Mechanism

[Chart: mechanism_breakdown.png]

[Narrative from data — hypothesis-driven basic research dominates over
cooperative agreements or contracts that might indicate validation work]

### 4. Explicit Biomarker Terminology Adoption

[Chart: explicit_adoption.png]

[Narrative from data]

## What This Cannot Tell Us

This keyword screen captures grants that *mention* biomarkers, not grants that *study*
biomarkers rigorously. It cannot distinguish:
- A grant developing a validated surrogate endpoint from one that mentions "biomarker" in passing
- Causal/mechanistic biomarker work from correlational/discovery work
- Grants with a clear estimand from those without

That's the job of the LLM grading pipeline (Phase 2).
```

- [ ] **Step 2: Run analyze.py and fill in actual numbers**

After `analyze.py` runs successfully, update SUMMARY.md with the actual numbers from `charts/funding_analysis.json`.

- [ ] **Step 3: Commit**

```bash
git add analysis/biomarker-screening/SUMMARY.md
git commit -m "analysis: add narrative summary for biomarker screening"
```

---

### Task 5: Update CLAUDE.md with Visualization Rule

**Files:**
- Modify: `CLAUDE.md:25-32` (Rules section)

- [ ] **Step 1: Add visualization rule to CLAUDE.md Rules section**

After the line `- **Don't invent scientific positions**...`, add:

```markdown
- **Visualization**: For analysis outputs and publication-quality charts, use Python data science
  libraries (seaborn, matplotlib, plotnine, bokeh) or Datawrapper. Chart.js is acceptable only
  for quick dev prototyping during iteration. Target: Datawrapper for final blog-ready figures.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add visualization standards to CLAUDE.md rules"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run full analysis end-to-end**

```bash
cd analysis/biomarker-screening && python analyze.py
```

Verify: 4 PNG charts in `charts/`, `funding_analysis.json` with correct totals.

- [ ] **Step 2: Run tests**

```bash
cd analysis/biomarker-screening && python -m pytest test_utils.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Lint**

```bash
ruff check analysis/biomarker-screening/ && ruff format analysis/biomarker-screening/
```

- [ ] **Step 4: Cross-check totals**

Verify `funding_analysis.json` summary matches `data/filtered/SUMMARY.md`:
- Total grants ≈ 269,630
- Explicit biomarker grants ≈ 75,849
- Total funding ≈ $134.49B
- Explicit funding ≈ $35.77B

- [ ] **Step 5: Push branch**

```bash
git push -u origin claude/add-download-skills-datasets-QIFS7
```
