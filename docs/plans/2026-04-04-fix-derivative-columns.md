# Fix derivative columns for abstract-only grants (Issue #35)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Compute MATCHED_CORE_TERMS, MATCHED_EXPANDED_TERMS, PRIMARY_TERM for all 344K grants. Currently missing for 68K abstract-only grants. No re-filtering needed — MATCHED_TERMS is correct and complete.

**Scope:** Fix two scripts, add integration tests, regenerate data and charts 7+8, replace v3.1 release.

---

### Task 1: Update `supplement_with_abstracts.py` to compute derivative columns

The `find_new_abstract_grants()` function (line 63–87) currently returns only `EXPLICIT_BIOMARKER` and `MATCHED_TERMS`. Add `MATCHED_CORE_TERMS`, `MATCHED_EXPANDED_TERMS`, `PRIMARY_TERM` using the same logic as `filter_biomarker_projects.py`.

**Step 1:** In `find_new_abstract_grants()`, after line 75 (`matched = find_matching_terms(...)`), compute:
```python
core_set = set(CORE_BIOMARKER_TERMS)
core_matched = [t for t in matched if t in core_set]
expanded_matched = [t for t in matched if t not in core_set]
```

**Step 2:** Update the dict at line 82–85 to include:
```python
"MATCHED_CORE_TERMS": ";".join(core_matched),
"MATCHED_EXPANDED_TERMS": ";".join(expanded_matched),
"PRIMARY_TERM": primary_term(matched),
```

**Step 3:** Import `primary_term` and `CORE_BIOMARKER_TERMS` from `keyword_terms` (already imported partially).

**Step 4:** Update `DEFAULT_COLUMNS` (line 336) to include the three new columns.

**Step 5:** Update the column-ensuring block (lines 440–444) to also ensure the three new columns.

**Step 6:** Update `process_year()` (lines 322–324) to write the three new columns from `new_grants[app_id]`.

**Step 7:** Run existing tests:
```bash
python3 -m unittest tests.test_supplement_with_abstracts -v
```

---

### Task 2: Add defensive backfill in `create_unified_dataset.py`

Even after fixing the source, `create_unified_dataset.py` should compute derivatives for any row where they're missing. This is the safety net.

**Step 1:** After reading and combining all CSVs (after deduplication), add:
```python
from keyword_terms import CORE_BIOMARKER_TERMS, primary_term

core_set = set(CORE_BIOMARKER_TERMS)

# Backfill derivative columns from MATCHED_TERMS where missing
mask = combined_df["PRIMARY_TERM"].isna() | (combined_df["PRIMARY_TERM"] == "")
has_mt = mask & combined_df["MATCHED_TERMS"].notna() & (combined_df["MATCHED_TERMS"] != "")

if has_mt.any():
    logger.info(f"Backfilling {has_mt.sum():,} rows with missing derivative columns")
    terms_series = combined_df.loc[has_mt, "MATCHED_TERMS"].str.split(";")
    combined_df.loc[has_mt, "PRIMARY_TERM"] = terms_series.apply(primary_term)
    combined_df.loc[has_mt, "MATCHED_CORE_TERMS"] = terms_series.apply(
        lambda ts: ";".join(t for t in ts if t in core_set))
    combined_df.loc[has_mt, "MATCHED_EXPANDED_TERMS"] = terms_series.apply(
        lambda ts: ";".join(t for t in ts if t not in core_set))
```

**Step 2:** Log how many rows were backfilled (should be ~68K now, 0 after Task 1 runs).

---

### Task 3: Add integration tests for column uniformity

Create `tests/test_pipeline_integrity.py` with tests that catch this class of error:

**Test 1: All rows have PRIMARY_TERM**
```python
def test_all_rows_have_primary_term(self):
    """Every grant in the unified dataset must have a PRIMARY_TERM."""
    empty = df[df["PRIMARY_TERM"].isna() | (df["PRIMARY_TERM"] == "")]
    self.assertEqual(len(empty), 0, f"{len(empty)} rows missing PRIMARY_TERM")
```

**Test 2: MATCHED_CORE + MATCHED_EXPANDED covers MATCHED_TERMS**
```python
def test_derivative_columns_cover_matched_terms(self):
    """MATCHED_CORE_TERMS + MATCHED_EXPANDED_TERMS must account for all MATCHED_TERMS."""
    for _, row in df.sample(500, random_state=42).iterrows():
        all_terms = set(row["MATCHED_TERMS"].split(";"))
        core = set(row["MATCHED_CORE_TERMS"].split(";")) if pd.notna(row["MATCHED_CORE_TERMS"]) and row["MATCHED_CORE_TERMS"] else set()
        expanded = set(row["MATCHED_EXPANDED_TERMS"].split(";")) if pd.notna(row["MATCHED_EXPANDED_TERMS"]) and row["MATCHED_EXPANDED_TERMS"] else set()
        self.assertEqual(all_terms, core | expanded)
```

**Test 3: EXPLICIT_BIOMARKER ↔ MATCHED_CORE_TERMS consistency**
```python
def test_explicit_biomarker_matches_core_terms(self):
    """EXPLICIT_BIOMARKER=TRUE iff MATCHED_CORE_TERMS is non-empty."""
    has_core = df["MATCHED_CORE_TERMS"].notna() & (df["MATCHED_CORE_TERMS"] != "")
    is_explicit = df["EXPLICIT_BIOMARKER"].astype(bool)
    mismatches = (has_core != is_explicit).sum()
    self.assertEqual(mismatches, 0, f"{mismatches} rows where EXPLICIT_BIOMARKER != (has core terms)")
```

**Test 4: Abstract and keyword CSVs have identical column sets**
```python
def test_csv_column_parity(self):
    """Keyword and abstract filtered CSVs must have the same columns."""
    kw_cols = set(pd.read_csv("data/filtered/keywords/biomarker_FY2024.csv", nrows=0).columns)
    abs_cols = set(pd.read_csv("data/filtered/biomarker_abstract_FY2024.csv", nrows=0).columns)
    # Abstract files may have slightly different raw columns, but must have all derivative columns
    required = {"MATCHED_TERMS", "MATCHED_CORE_TERMS", "MATCHED_EXPANDED_TERMS", "PRIMARY_TERM", "EXPLICIT_BIOMARKER"}
    self.assertTrue(required.issubset(abs_cols), f"Abstract CSV missing: {required - abs_cols}")
```

**Test 5: Keyword term list changes are covered**
```python
def test_term_priority_covers_all_terms(self):
    """TERM_PRIORITY must contain every term in EXPANDED_BIOMARKER_TERMS."""
    from scripts.keyword_terms import TERM_PRIORITY, EXPANDED_BIOMARKER_TERMS
    missing = set(EXPANDED_BIOMARKER_TERMS) - set(TERM_PRIORITY)
    self.assertEqual(missing, set(), f"Terms missing from TERM_PRIORITY: {missing}")
```

---

### Task 4: Re-run abstract filter and regenerate unified dataset

**Step 1:** Re-run abstract filter (uses updated script from Task 1):
```bash
python3 scripts/supplement_with_abstracts.py \
  --abs-dir ~/Downloads \
  --raw-dir ~/Downloads \
  --filtered-dir data/filtered
```

**Step 2:** Regenerate unified dataset (backfill from Task 2 as safety net):
```bash
python3 scripts/create_unified_dataset.py
```

**Step 3:** Verify:
```bash
python3 -m unittest tests.test_pipeline_integrity -v
```

All 5 tests must pass.

---

### Task 5: Regenerate affected charts and release

**Step 1:** Remove the load-time PRIMARY_TERM patch from `analysis/biomarker-screening/utils.py` (lines 49–60). It should no longer be needed.

**Step 2:** Regenerate charts:
```bash
python3 analysis/biomarker-screening/analyze.py
```

Verify charts 7 and 8 reflect the full 344K grants.

**Step 3:** Republish Datawrapper charts (charts 7 and 8 only):
```bash
export $(grep DATAWRAPPER_API_TOKEN /path/to/.env)
python3 analysis/biomarker-screening/analyze.py
```

**Step 4:** Replace v3.1 release:
```bash
gh release delete dataset-release-v3.1 --repo surrogate-sci/nih-biomarker-funding -y
gh release create dataset-release-v3.1 \
  --repo surrogate-sci/nih-biomarker-funding \
  --title "Dataset v3.1 — enriched keyword columns (fixed)" \
  --notes "..." \
  data/nih_biomarker_unified_2004-2024.csv
```

**Step 5:** Copy verified data to main repo:
```bash
cp data/nih_biomarker_unified_2004-2024.csv /path/to/main/repo/data/
cp data/filtered/biomarker_abstract_FY*.csv /path/to/main/repo/data/filtered/
```

---

### Task 6: Commit, push, verify CI

**Step 1:** Commit all changes:
```bash
git add scripts/supplement_with_abstracts.py scripts/create_unified_dataset.py \
  tests/test_pipeline_integrity.py analysis/biomarker-screening/utils.py \
  analysis/biomarker-screening/charts/keyword_funding.png \
  analysis/biomarker-screening/charts/core_vs_expanded_terms.png \
  analysis/biomarker-screening/charts/funding_analysis.json
git commit -m "data: compute derivative columns for all grants, add pipeline integrity tests (fixes #35)"
```

**Step 2:** Run full test suite:
```bash
python3 -m unittest discover tests -v
```

**Step 3:** Push and verify PR #32 is unblocked.
