# Union Keyword Filter + General Sampling Script

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the keyword filter to search ABSTRACT_TEXT across ALL 21 years (union with existing PROJECT_TERMS/TITLE matches), add a `MATCH_SOURCE` provenance column, rebuild the unified dataset, then build `sample_grants.py` for an ~18K pilot across 12 NIH institutes.

**Architecture:** A new script `supplement_with_abstracts.py` reads abstract zips for all years, applies the same expanded/core keyword search to ABSTRACT_TEXT, and merges newly-found grants into the existing filtered year CSVs and unified dataset. Each grant gets a `MATCH_SOURCE` column tracking where the keyword matched (keywords_only, abstract_only, keyword_abstract). The LLM rubric grading will later validate which grants are truly biomarker research — `MATCH_SOURCE` enables analysis of false-positive rates per source. Then `sample_grants.py` replaces the hardcoded NCI logic with configurable IC selection, tiered sampling rates, and a per-stratum floor.

**Tech Stack:** Python 3.10+, csv, zipfile (stdlib only — no new deps). Reuses `abstract_loader.py` and keyword logic from `filter_biomarker_projects.py`.

---

## Part A: Union Keyword Filter with Abstract Text (Issue #11)

### Context

The filtering pipeline searches `PROJECT_TITLE` and `PROJECT_TERMS` columns. Abstract text is a complementary source — even in healthy years, ~2,500-2,800 grants match in abstracts but not in PROJECT_TERMS/TITLE.

Overlap analysis (keyword = PROJECT_TERMS/TITLE, abstract = ABSTRACT_TEXT):

| Year | Keyword | Abstract | Both | Keyword-only | Abstract-only | Union |
|------|---------|----------|------|-------------|--------------|-------|
| FY2005 | 327 | 3,792 | 207 | 120 | 3,585 | 3,912 |
| FY2006 | 336 | 4,213 | 226 | 110 | 3,987 | 4,323 |
| FY2012 | 13,628 | 8,924 | 7,765 | 5,863 | 1,159 | 14,787 |
| FY2013 | 4,182 | 8,760 | 2,508 | 1,674 | 6,252 | 10,434 |
| FY2018 | 8,435 | 13,387 | 5,000 | 3,435 | 8,387 | 16,822 |
| FY2019 | 19,148 | 13,112 | 10,339 | 8,809 | 2,773 | 21,921 |
| FY2022 | 22,048 | 14,485 | 11,690 | 10,358 | 2,795 | 24,843 |
| FY2024 | 23,252 | 13,865 | 11,454 | 11,798 | 2,411 | 25,663 |

The two sources are complementary: PROJECT_TERMS is a controlled vocabulary (catches grants tagged but not mentioning biomarkers in prose), ABSTRACT_TEXT is free text (catches grants describing biomarker work without tagged terms).

**Provenance:** Each grant gets a `MATCH_SOURCE` column:
- `keywords_only` — matched in PROJECT_TERMS or PROJECT_TITLE but not ABSTRACT_TEXT
- `abstract_only` — matched in ABSTRACT_TEXT but not PROJECT_TERMS/TITLE
- `keyword_abstract` — matched in both sources

This enables the pilot grading to validate false-positive rates per source (abstract-only grants may have higher noise).

Abstract zips exist for all 21 years at `~/Downloads/RePORTER_PRJABS_C_FY{year}.zip` (including FY2016).

### Task 1: Extract keyword matching into a shared module

The keyword logic (`contains_biomarker_terms`, `CORE_BIOMARKER_TERMS`, `EXPANDED_BIOMARKER_TERMS`) lives in `filter_biomarker_projects.py` but can't be imported because that file imports `requests` at module level. Extract the pure keyword functions into `scripts/keyword_terms.py`.

**Files:**
- Create: `scripts/keyword_terms.py`
- Modify: `scripts/filter_biomarker_projects.py` (import from keyword_terms)
- Test: `tests/test_keyword_terms.py`

**Step 1: Write the failing test**

```python
# tests/test_keyword_terms.py
"""Tests for keyword matching logic."""
import unittest


class TestContainsBiomarkerTerms(unittest.TestCase):
    def test_simple_match(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertTrue(contains_biomarker_terms("This is a biomarker study", ["biomarker"]))

    def test_no_match(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms("This is a cancer study", ["biomarker"]))

    def test_and_condition_match(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertTrue(contains_biomarker_terms("clinical omics study", ["clinical+omics"]))

    def test_and_condition_partial(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms("clinical study", ["clinical+omics"]))

    def test_case_insensitive(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertTrue(contains_biomarker_terms("BIOMARKER study", ["biomarker"]))

    def test_empty_text(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms("", ["biomarker"]))

    def test_none_text(self):
        from scripts.keyword_terms import contains_biomarker_terms
        self.assertFalse(contains_biomarker_terms(None, ["biomarker"]))

    def test_core_terms_defined(self):
        from scripts.keyword_terms import CORE_BIOMARKER_TERMS
        self.assertEqual(len(CORE_BIOMARKER_TERMS), 4)
        self.assertIn("biomarker", CORE_BIOMARKER_TERMS)

    def test_expanded_terms_defined(self):
        from scripts.keyword_terms import EXPANDED_BIOMARKER_TERMS
        self.assertEqual(len(EXPANDED_BIOMARKER_TERMS), 10)
        self.assertIn("endophenotype", EXPANDED_BIOMARKER_TERMS)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_keyword_terms.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.keyword_terms'`

**Step 3: Create `scripts/keyword_terms.py`**

Move `contains_biomarker_terms`, `CORE_BIOMARKER_TERMS`, and `EXPANDED_BIOMARKER_TERMS` from `filter_biomarker_projects.py` into this new file. In `filter_biomarker_projects.py`, replace the definitions with:

```python
from scripts.keyword_terms import (
    contains_biomarker_terms,
    CORE_BIOMARKER_TERMS,
    EXPANDED_BIOMARKER_TERMS,
)
```

The new file contains no `requests` import, so it's safely importable from any script.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_keyword_terms.py -v`
Expected: all 9 PASS

**Step 5: Commit**

```bash
git add scripts/keyword_terms.py tests/test_keyword_terms.py scripts/filter_biomarker_projects.py
git commit -m "refactor: extract keyword matching into scripts/keyword_terms.py"
```

---

### Task 2: Build `supplement_with_abstracts.py`

For each year (all 21): load all abstracts from the zip, run expanded keyword search on ABSTRACT_TEXT, identify grants NOT already in the filtered year CSV, join project metadata from the raw project CSV, and write to a **separate** file (`biomarker_abstract_FY{year}.csv`). The original keyword-filtered files are never modified.

**File layout:**
- `data/filtered/biomarker_FY2005.csv` — original keyword matches (untouched)
- `data/filtered/biomarker_abstract_FY2005.csv` — abstract-only matches (new)

`create_unified_dataset.py` reads both patterns, unions them, deduplicates, and assigns `MATCH_SOURCE` at merge time (keywords_only, abstract_only, keyword_abstract). This is idempotent — re-running the abstract script overwrites the abstract files without corrupting the originals.

**Files:**
- Create: `scripts/supplement_with_abstracts.py`
- Test: `tests/test_supplement_with_abstracts.py`

**Step 1: Write the failing test**

```python
# tests/test_supplement_with_abstracts.py
"""Tests for abstract-text supplementation logic."""
import unittest


class TestFindNewGrants(unittest.TestCase):
    """Test the core logic: find grants in abstracts that match keywords but aren't already filtered."""

    def test_finds_new_grant(self):
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        existing_ids = {"111"}
        abstracts = {
            "111": "existing biomarker grant",
            "222": "new biomarker discovery study",
            "333": "unrelated cancer treatment",
        }
        new_grants = find_new_grants_from_abstracts(abstracts, existing_ids)
        self.assertIn("222", new_grants)
        self.assertNotIn("111", new_grants)  # already exists
        self.assertNotIn("333", new_grants)  # no keyword match

    def test_sets_explicit_biomarker_flag(self):
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        abstracts = {
            "100": "This studies a specific biomarker for disease",
            "200": "Clinical imaging analysis of tumors",  # matches clinical+imaging
        }
        new_grants = find_new_grants_from_abstracts(abstracts, set())
        self.assertEqual(new_grants["100"]["EXPLICIT_BIOMARKER"], "TRUE")
        self.assertEqual(new_grants["200"]["EXPLICIT_BIOMARKER"], "FALSE")

    def test_empty_abstracts(self):
        from scripts.supplement_with_abstracts import find_new_grants_from_abstracts

        new_grants = find_new_grants_from_abstracts({}, set())
        self.assertEqual(len(new_grants), 0)


class TestAssignMatchSource(unittest.TestCase):
    """Test MATCH_SOURCE provenance tagging."""

    def test_keywords_only(self):
        from scripts.supplement_with_abstracts import assign_match_source

        # Grant matches in PROJECT_TERMS but not in abstract
        result = assign_match_source(
            app_id="100", in_keyword_filter=True, abstract_text="unrelated study",
        )
        self.assertEqual(result, "keywords_only")

    def test_abstract_only(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="200", in_keyword_filter=False, abstract_text="biomarker validation study",
        )
        self.assertEqual(result, "abstract_only")

    def test_keyword_abstract(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="300", in_keyword_filter=True, abstract_text="biomarker discovery project",
        )
        self.assertEqual(result, "keyword_abstract")

    def test_no_abstract(self):
        from scripts.supplement_with_abstracts import assign_match_source

        result = assign_match_source(
            app_id="400", in_keyword_filter=True, abstract_text="",
        )
        self.assertEqual(result, "keywords_only")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_supplement_with_abstracts.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write `scripts/supplement_with_abstracts.py`**

```python
#!/usr/bin/env python3
"""
Filter grants by biomarker keywords in abstract text, writing separate per-year CSVs.

For each fiscal year:
1. Loads all abstracts from RePORTER zip files
2. Applies expanded keyword search to ABSTRACT_TEXT
3. Identifies grants NOT already in the keyword-filtered year CSV
4. Joins project metadata from raw RePORTER project CSV
5. Writes abstract-only matches to data/filtered/biomarker_abstract_FY{year}.csv

Original keyword-filtered files are never modified.
MATCH_SOURCE assignment happens downstream in create_unified_dataset.py.

Usage:
    python3 scripts/supplement_with_abstracts.py --abs-dir ~/Downloads --raw-dir ~/Downloads
    python3 scripts/supplement_with_abstracts.py --years 2005 2006 --dry-run
"""

import argparse
import csv
import io
import logging
import zipfile
from pathlib import Path

from scripts.keyword_terms import (
    contains_biomarker_terms,
    CORE_BIOMARKER_TERMS,
    EXPANDED_BIOMARKER_TERMS,
)

ALL_YEARS = list(range(2004, 2025))


def find_new_grants_from_abstracts(
    abstracts: dict[str, str],
    existing_ids: set[str],
    expanded_terms: list[str] | None = None,
    core_terms: list[str] | None = None,
) -> dict[str, dict]:
    """Identify grants matching keyword search in abstract text that aren't already filtered.

    Returns dict mapping APPLICATION_ID -> {"ABSTRACT_TEXT": ..., "EXPLICIT_BIOMARKER": ...}
    """
    if expanded_terms is None:
        expanded_terms = EXPANDED_BIOMARKER_TERMS
    if core_terms is None:
        core_terms = CORE_BIOMARKER_TERMS

    new_grants = {}
    for app_id, abstract in abstracts.items():
        if app_id in existing_ids:
            continue
        if contains_biomarker_terms(abstract, expanded_terms):
            is_explicit = contains_biomarker_terms(abstract, core_terms)
            new_grants[app_id] = {
                "ABSTRACT_TEXT": abstract,
                "EXPLICIT_BIOMARKER": "TRUE" if is_explicit else "FALSE",
            }
    return new_grants


def assign_match_source(
    app_id: str,
    in_keyword_filter: bool,
    abstract_text: str,
    expanded_terms: list[str] | None = None,
) -> str:
    """Determine MATCH_SOURCE for a grant.

    Returns "keywords_only", "abstract_only", or "keyword_abstract".
    """
    if expanded_terms is None:
        expanded_terms = EXPANDED_BIOMARKER_TERMS

    abstract_match = bool(abstract_text) and contains_biomarker_terms(abstract_text, expanded_terms)

    if in_keyword_filter and abstract_match:
        return "keyword_abstract"
    elif in_keyword_filter:
        return "keywords_only"
    else:
        return "abstract_only"
```

The full script `main()` includes:
- `--abs-dir` — path to RePORTER abstract zips (default ~/Downloads)
- `--raw-dir` — path to raw RePORTER project CSVs (default ~/Downloads) for joining project metadata
- `--years` — which years to process (default: all 21)
- `--filtered-dir` — path to filtered year CSVs (default: data/filtered/) for reading existing keyword matches
- `--dry-run` — report what would be found without writing files
- For each year:
  1. Load existing `biomarker_FY{year}.csv` and collect APPLICATION_IDs
  2. Load abstracts from zip, run keyword search, find grants not in existing set
  3. Load raw project CSV (`RePORTER_PRJ_C_FY{year}.csv`), join full metadata for new grants
  4. Write new grants to `data/filtered/biomarker_abstract_FY{year}.csv` (overwrites previous run — idempotent)
- Prints per-year summary: keyword-only count, abstract-only count, overlap estimate

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_supplement_with_abstracts.py -v`
Expected: all 7 PASS

**Step 5: Commit**

```bash
git add scripts/supplement_with_abstracts.py tests/test_supplement_with_abstracts.py
git commit -m "feat: add supplement_with_abstracts.py for union keyword filter (Issue #11)"
```

---

### Task 3: Run abstract filtering on all 21 years

**Step 1: Dry run first**

```bash
python3 scripts/supplement_with_abstracts.py --abs-dir ~/Downloads --raw-dir ~/Downloads --dry-run
```

Expected output: per-year count of abstract-only grants found, no files written. Expect ~1,000-8,000 new grants per year depending on PROJECT_TERMS coverage.

**Step 2: Run for real**

```bash
python3 scripts/supplement_with_abstracts.py --abs-dir ~/Downloads --raw-dir ~/Downloads
```

This writes `data/filtered/biomarker_abstract_FY{year}.csv` for each year. Original `biomarker_FY{year}.csv` files are untouched.

**Step 3: Update `create_unified_dataset.py` to union both file sets**

Modify `create_unified_dataset.py`:
- Read both `biomarker_FY*.csv` (keyword) and `biomarker_abstract_FY*.csv` (abstract-only) patterns
- Deduplicate by (APPLICATION_ID, FY) — keyword files take precedence for metadata
- Assign `MATCH_SOURCE` column:
  - `keywords_only` — only in `biomarker_FY{year}.csv`
  - `abstract_only` — only in `biomarker_abstract_FY{year}.csv`
  - `keyword_abstract` — in both (use keyword file's row for metadata, but note the abstract also matched)
- To determine `keyword_abstract`, need to check whether keyword-file grants also have abstract matches — load abstract IDs per year for this lookup
- Add `MATCH_SOURCE` to `COLUMNS_TO_KEEP`

```bash
python3 scripts/create_unified_dataset.py
```

**Step 4: Verify counts and provenance**

```bash
python3 -c "
import csv
from collections import Counter
with open('data/nih_biomarker_unified_2004-2024.csv') as f:
    rows = list(csv.DictReader(f))
by_year = Counter(r['FY'] for r in rows)
by_source = Counter(r.get('MATCH_SOURCE','') for r in rows)
print(f'Total grants: {len(rows)}')
print(f'MATCH_SOURCE: {dict(by_source)}')
for y in sorted(by_year):
    print(f'  FY{y}: {by_year[y]}')"
```

Expected: ~300K+ total (up from 270K), with MATCH_SOURCE breakdown showing keywords_only, abstract_only, keyword_abstract.

**Step 5: Commit**

```bash
git add -f data/filtered/biomarker_abstract_FY*.csv scripts/create_unified_dataset.py \
  data/nih_biomarker_unified_2004-2024.csv
git commit -m "data: union keyword + abstract filter across all 21 years (Issue #11)"
```

**Note:** FY2016 abstracts zip exists (`~/Downloads/RePORTER_PRJABS_C_FY2016.zip`). The previous "FY2016 missing" note in `abstract_loader.py` should be corrected.

---

## Part B: General Sampling Script (Issue #19)

### Task 5: Build `sample_grants.py`

**Files:**
- Create: `scripts/sample_grants.py`
- Test: `tests/test_sample_grants.py`

**Step 1: Write the failing tests**

```python
# tests/test_sample_grants.py
"""Tests for general-purpose grant sampling."""
import csv
import tempfile
import unittest
from pathlib import Path


def make_test_csv(rows, path):
    """Write rows (list of dicts) to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


class TestAssignRates(unittest.TestCase):
    def test_ca_gets_5_percent(self):
        from scripts.sample_grants import assign_rate
        self.assertAlmostEqual(assign_rate("CA", 66000), 0.05)

    def test_large_ic_gets_7_percent(self):
        from scripts.sample_grants import assign_rate
        self.assertAlmostEqual(assign_rate("HL", 23000), 0.07)

    def test_small_ic_gets_10_percent(self):
        from scripts.sample_grants import assign_rate
        self.assertAlmostEqual(assign_rate("DA", 7000), 0.10)


class TestStratifiedSample(unittest.TestCase):
    def test_respects_min_per_stratum(self):
        from scripts.sample_grants import stratified_sample

        # 10 grants for IC=XX in FY2020, rate=0.10 -> 1, but min=25 -> take all 10
        rows = [
            {"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "XX"}
            for i in range(10)
        ]
        sampled = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        self.assertEqual(len(sampled), 10)  # can't exceed pool

    def test_rate_applied(self):
        from scripts.sample_grants import stratified_sample

        rows = [
            {"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "CA"}
            for i in range(1000)
        ]
        sampled = stratified_sample(rows, rate=0.05, min_per_stratum=25, seed=42)
        self.assertAlmostEqual(len(sampled), 50, delta=5)

    def test_reproducible_with_seed(self):
        from scripts.sample_grants import stratified_sample

        rows = [
            {"APPLICATION_ID": str(i), "FY": "2020", "ADMINISTERING_IC": "CA"}
            for i in range(1000)
        ]
        s1 = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        s2 = stratified_sample(rows, rate=0.10, min_per_stratum=25, seed=42)
        ids1 = [r["APPLICATION_ID"] for r in s1]
        ids2 = [r["APPLICATION_ID"] for r in s2]
        self.assertEqual(ids1, ids2)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sample_grants.py -v`
Expected: FAIL

**Step 3: Write `scripts/sample_grants.py`**

Key design:
- `assign_rate(ic, pool_size)` — CA: 0.05, >=20K: 0.07, <20K: 0.10
- `stratified_sample(rows, rate, min_per_stratum, seed)` — stratify by FY, apply rate with floor
- `main()` with args:
  - `--unified` — path to unified dataset
  - `--abs-dir` — path to abstract zips
  - `--ics` — list of IC codes (default: top 12)
  - `--rate` — override rate for all ICs (omit for tiered defaults)
  - `--min-per-stratum` — floor per IC×FY (default: 25)
  - `--seed` — random seed (default: 42)
  - `--output` — output path (default auto-generated)
  - `--skip-years` — years to skip (default: none; FY2016 no longer skipped if zip exists)
- Reuses `abstract_loader.py` for abstract join
- Output columns match `sample_oncology.py` format

Top 12 ICs (hardcoded default):
```python
DEFAULT_ICS = ["CA", "HL", "AG", "AI", "NS", "MH", "DK", "HD", "GM", "DA", "EB", "AR"]
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sample_grants.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add scripts/sample_grants.py tests/test_sample_grants.py
git commit -m "feat: add sample_grants.py with tiered rates for 12 ICs (Issue #19)"
```

---

### Task 6: Run pilot sampling

**Step 1: Dry run to verify counts**

```bash
python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv \
    --abs-dir ~/Downloads --seed 42 --dry-run
```

Expected: ~18,300 grants across 12 ICs, per-IC and per-year breakdown printed.

**Step 2: Full run**

```bash
python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv \
    --abs-dir ~/Downloads --seed 42 --output data/pilot_sample_12IC_5pct_seed42.csv
```

**Step 3: Verify output**

```bash
python3 -c "
import csv
from collections import Counter
with open('data/pilot_sample_12IC_5pct_seed42.csv') as f:
    rows = list(csv.DictReader(f))
print(f'Total: {len(rows)}')
ic_counts = Counter(r['ADMINISTERING_IC'] for r in rows)
for ic, n in ic_counts.most_common():
    print(f'  {ic}: {n}')
has_abs = sum(1 for r in rows if r['HAS_ABSTRACT'] == 'True')
print(f'With abstracts: {has_abs} ({100*has_abs/len(rows):.1f}%)')
"
```

**Step 4: Commit sample**

```bash
git add -f data/pilot_sample_12IC_5pct_seed42.csv
git commit -m "data: add 18K pilot sample across 12 ICs (Issue #19)"
```

---

## Dependency chain

```
Task 1 (extract keyword_terms.py)
  → Task 2 (supplement_with_abstracts.py)
    → Task 3 (run union filter on all 21 years, rebuild unified dataset)
      → Task 5 (sample_grants.py)
        → Task 6 (run pilot sampling)
```

## What this unblocks

- Issue #11 closed after Task 3
- Issue #19 closed after Task 6
- Pilot Inspect eval: `inspect eval inspect_task.py -T dataset_path=data/pilot_sample_12IC_5pct_seed42.csv --model google/gemini-2.5-flash-lite --max-connections 20`
- Pilot results enable analysis of false-positive rates by MATCH_SOURCE (do abstract_only grants grade differently on Dim1?)
