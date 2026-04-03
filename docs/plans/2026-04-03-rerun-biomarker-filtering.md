# Re-run Biomarker Filtering with Expanded Keywords Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Re-filter all 1.7M NIH ExPORTER grants (FY2004-2024) using the updated keyword tiers (13 core / 36 expanded) and facility grant screening, then re-filter abstracts and regenerate the unified dataset.

**Architecture:** Two filtering passes produce the 332K-grant dataset:
1. **Keyword filter** (`process_all_years.py` → `filter_biomarker_projects.py`): searches PROJECT_TITLE + PROJECT_TERMS → `data/filtered/keywords/biomarker_FY*.csv`
2. **Abstract filter** (`supplement_with_abstracts.py`): searches ABSTRACT_TEXT for grants NOT already caught by keywords → `data/filtered/abstracts/biomarker_abstract_FY*.csv`
3. **Union** (`create_unified_dataset.py`): combines both sources with `MATCH_SOURCE` column → `data/nih_biomarker_unified_2004-2024.csv`

**Important:** `supplement_with_abstracts.py`, `keyword_terms.py`, and the updated `create_unified_dataset.py` merged to main via PRs #22 and #25, but AFTER this branch was created. Task 0 rebases onto `origin/main` to pick these up.

**Tech Stack:** Python 3, csv, pandas

---

### Task 0: Rebase onto origin/main

PRs #22 (abstract filter + union) and #25 (row fix + dataset v2.0) merged to main after this branch was created. Rebase to pick up `supplement_with_abstracts.py`, `keyword_terms.py`, and updated `create_unified_dataset.py`.

**Step 1: Rebase**

```bash
git fetch origin main
git rebase origin/main
```

**Step 2: Resolve conflicts**

Likely conflicts in `filter_biomarker_projects.py` (our keyword changes vs PR #22's refactor) and possibly `create_unified_dataset.py`. Ensure our new term lists and facility screening survive the merge.

Also check: `keyword_terms.py` may define its own term lists. If so, update them to match our new core/expanded terms, or ensure it imports from `filter_biomarker_projects.py`.

**Step 3: Run all tests**

```bash
python3 -m unittest discover tests -v
```

---

### Task 1: Dry-run keyword filter on one year

**Step 1: Run filter on FY2022**

```bash
python3 scripts/process_all_years.py \
  --start-year 2022 --end-year 2022 \
  --skip-download \
  --raw-dir ~/Downloads \
  --filtered-dir data/filtered/keywords \
  --term-set expanded \
  --verbose
```

Expected: new term counts, "Facility grants excluded: N" in output.

**Step 2: Compare old vs new counts**

```bash
git show HEAD:data/filtered/keywords/biomarker_FY2022.csv | wc -l
wc -l data/filtered/keywords/biomarker_FY2022.csv
```

**Step 3: Commit single-year test**

```bash
git add -f data/filtered/keywords/biomarker_FY2022.csv
git commit -m "filter: test rerun FY2022 with expanded keywords and facility screening"
```

---

### Task 2: Re-filter all 21 fiscal years (keywords)

**Step 1: Run batch filter**

```bash
python3 scripts/process_all_years.py \
  --start-year 2004 --end-year 2024 \
  --skip-download \
  --raw-dir ~/Downloads \
  --filtered-dir data/filtered/keywords \
  --term-set expanded \
  --verbose
```

~30-60 min for 1.7M grants.

**Step 2: Verify 21 output files**

```bash
ls data/filtered/keywords/biomarker_FY*.csv | wc -l
# Expected: 21
```

**Step 3: Commit**

```bash
git add -f data/filtered/keywords/biomarker_FY*.csv
git commit -m "filter: rerun all FY2004-2024 with expanded keywords and facility screening"
```

---

### Task 3: Re-filter abstracts

Abstract filtering searches ABSTRACT_TEXT for biomarker terms in grants NOT already caught by keyword filter. Uses `supplement_with_abstracts.py`.

**Step 1: Run abstract filter for all years**

```bash
python3 scripts/supplement_with_abstracts.py \
  --abs-dir ~/Downloads \
  --keyword-dir data/filtered/keywords \
  --output-dir data/filtered/abstracts \
  --start-year 2004 --end-year 2024
```

(Verify exact CLI args — may differ based on PR #22 implementation)

**Step 2: Verify output**

```bash
ls data/filtered/abstracts/biomarker_abstract_FY*.csv | wc -l
# Expected: 21 (or 20 if FY2016 abstracts missing)
```

**Step 3: Commit**

```bash
git add -f data/filtered/abstracts/biomarker_abstract_FY*.csv
git commit -m "filter: rerun abstract filter with expanded keywords"
```

---

### Task 4: Regenerate unified dataset (keyword + abstract union)

**Step 1: Run unified dataset creation**

```bash
python3 scripts/create_unified_dataset.py \
  --filtered-dir data/filtered \
  --output data/nih_biomarker_unified_2004-2024.csv
```

(The updated `create_unified_dataset.py` from PR #22 reads both `keywords/` and `abstracts/` subdirs and adds `MATCH_SOURCE` column)

**Step 2: Verify row count, columns, no double counting**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/nih_biomarker_unified_2004-2024.csv')
print(f'Rows: {len(df):,}')
print(f'EXPLICIT_BIOMARKER TRUE: {(df.EXPLICIT_BIOMARKER == True).sum():,}')
print(f'EXPLICIT_BIOMARKER FALSE: {(df.EXPLICIT_BIOMARKER == False).sum():,}')
print(f'MATCH_SOURCE distribution:')
print(df.MATCH_SOURCE.value_counts())
dupes = df.duplicated(subset=['APPLICATION_ID', 'FY'], keep=False)
assert dupes.sum() == 0, 'DOUBLE COUNTING DETECTED'
print('No double counting — OK')
"
```

**Step 3: Commit**

```bash
git add -f data/nih_biomarker_unified_2004-2024.csv
git commit -m "data: regenerate unified dataset with expanded keywords"
```

---

### Task 5: Regenerate summaries

**Step 1: Regenerate keyword summary**

```bash
python3 scripts/generate_summary.py \
  --filtered-dir data/filtered/keywords \
  --output data/filtered/keywords/SUMMARY.md
```

**Step 2: Review key numbers** — total grants, EXPLICIT_BIOMARKER count, facility exclusions

**Step 3: Commit**

```bash
git add -f data/filtered/keywords/SUMMARY.md data/filtered/SUMMARY.md
git commit -m "data: regenerate summaries with expanded keyword results"
```

---

### Task 6: Run tests and push

**Step 1: Run all tests**

```bash
python3 -m unittest discover tests -v
```

**Step 2: Push**

```bash
git push
```

---

### Task 7: Update issue #27 with before/after results

Comment on issue with actual numbers from Tasks 2-4.
