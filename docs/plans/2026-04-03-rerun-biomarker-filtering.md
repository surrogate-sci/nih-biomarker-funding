# Re-run Biomarker Filtering with Expanded Keywords Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Re-filter all 1.7M NIH ExPORTER grants (FY2004-2024) using the updated keyword tiers (13 core / 36 expanded) and facility grant screening, then regenerate the unified dataset and summary.

**Architecture:** `process_all_years.py` calls `filter_biomarker_projects.py` per year via subprocess. The filter script now has expanded terms and `is_facility_grant()` screening. After filtering, `create_unified_dataset.py` merges year files and `generate_summary.py` produces stats. The raw ExPORTER ZIPs live in `~/Downloads/`, filtered output goes to `data/filtered/keywords/`.

**Tech Stack:** Python 3, csv, pandas. No external dependencies beyond what's already installed.

---

### Task 1: Fix process_all_years.py to pass raw-dir correctly

`process_all_years.py` expects extracted CSVs in `--raw-dir`. Our ZIPs are in `~/Downloads/` and the script can extract them. But it needs to handle the case where ZIPs exist but CSVs don't (it already does — lines 130-166). No code change needed, just the right CLI args.

**Files:**
- Verify: `scripts/process_all_years.py` (read-only, confirm it handles ~/Downloads ZIPs)

**Step 1: Dry-run one year to verify the pipeline works end-to-end**

Run:
```bash
python3 scripts/process_all_years.py \
  --start-year 2022 --end-year 2022 \
  --skip-download \
  --raw-dir ~/Downloads \
  --filtered-dir data/filtered/keywords \
  --term-set expanded \
  --verbose
```

Expected: `data/filtered/keywords/biomarker_FY2022.csv` regenerated with new term counts. Should see "Facility grants excluded: N" in output.

**Step 2: Compare old vs new counts for FY2022**

```bash
# Old count (before overwrite — check git):
git show HEAD:data/filtered/keywords/biomarker_FY2022.csv | wc -l

# New count:
wc -l data/filtered/keywords/biomarker_FY2022.csv
```

Expected: New count should be higher (more terms) minus facility exclusions.

**Step 3: Commit single-year test result**

```bash
git add data/filtered/keywords/biomarker_FY2022.csv
git commit -m "filter: test rerun FY2022 with expanded keywords and facility screening"
```

---

### Task 2: Re-filter all 21 fiscal years

**Files:**
- Modify: `data/filtered/keywords/biomarker_FY{2004..2024}.csv` (21 files, overwritten)

**Step 1: Run batch filter for all years**

```bash
python3 scripts/process_all_years.py \
  --start-year 2004 --end-year 2024 \
  --skip-download \
  --raw-dir ~/Downloads \
  --filtered-dir data/filtered/keywords \
  --term-set expanded \
  --verbose
```

Time estimate: ~30-60 min for 1.7M grants across 21 ZIPs.

**Step 2: Verify all 21 output files exist**

```bash
ls -la data/filtered/keywords/biomarker_FY*.csv | wc -l
# Expected: 21
```

**Step 3: Spot-check facility exclusion counts in log output**

Grep the output for "Facility grants excluded" — should be non-zero for most years.

**Step 4: Commit filtered files**

```bash
git add -f data/filtered/keywords/biomarker_FY*.csv
git commit -m "filter: rerun all FY2004-2024 with expanded keywords and facility screening"
```

---

### Task 3: Regenerate summary statistics

**Files:**
- Modify: `data/filtered/keywords/SUMMARY.md` (overwritten)

**Step 1: Run summary generator**

```bash
python3 scripts/generate_summary.py \
  --filtered-dir data/filtered/keywords \
  --output data/filtered/keywords/SUMMARY.md
```

**Step 2: Review key numbers**

Check SUMMARY.md for:
- Total matched projects (should be higher than previous ~270K/~330K)
- EXPLICIT_BIOMARKER count (should be higher — core now has 13 terms vs 4)
- FY2005/2006 still show expected data quality degradation

**Step 3: Commit summary**

```bash
git add -f data/filtered/keywords/SUMMARY.md
git commit -m "data: regenerate summary with expanded keyword results"
```

---

### Task 4: Regenerate unified dataset

**Files:**
- Modify: `data/nih_biomarker_unified_2004-2024.csv` (overwritten)

**Step 1: Run unified dataset creation**

```bash
python3 scripts/create_unified_dataset.py \
  --filtered-dir data/filtered/keywords \
  --output data/nih_biomarker_unified_2004-2024.csv
```

**Step 2: Verify row count and columns**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/nih_biomarker_unified_2004-2024.csv')
print(f'Rows: {len(df):,}')
print(f'Columns: {len(df.columns)}')
print(f'EXPLICIT_BIOMARKER TRUE: {(df.EXPLICIT_BIOMARKER == True).sum():,}')
print(f'EXPLICIT_BIOMARKER FALSE: {(df.EXPLICIT_BIOMARKER == False).sum():,}')
print(f'FY range: {df.FY.min()}-{df.FY.max()}')
"
```

Expected: Row count > previous unified dataset. No double-counted grants (unique APPLICATION_ID+FY).

**Step 3: Verify no double counting**

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/nih_biomarker_unified_2004-2024.csv')
dupes = df.duplicated(subset=['APPLICATION_ID', 'FY'], keep=False)
print(f'Duplicate (APP_ID, FY) pairs: {dupes.sum()}')
assert dupes.sum() == 0, 'DOUBLE COUNTING DETECTED'
print('No double counting — OK')
"
```

**Step 4: Commit unified dataset**

```bash
git add -f data/nih_biomarker_unified_2004-2024.csv
git commit -m "data: regenerate unified dataset with expanded keywords"
```

---

### Task 5: Run tests and push

**Files:**
- Test: `tests/test_filter_biomarker_projects.py`

**Step 1: Run filter tests**

```bash
python3 -m unittest tests.test_filter_biomarker_projects -v
```

Expected: All 30 tests pass.

**Step 2: Push branch**

```bash
git push
```

---

### Task 6: Update issue #27 with results

**Step 1: Comment on issue with before/after comparison**

```bash
gh issue comment 27 --body "$(cat <<'EOF'
## Results: keyword expansion and re-filtering

Refiltered all FY2004-2024 with updated tiers:
- **Core**: 13 terms (was 4) — added endophenotype, intermediate outcome/endpoint, digital endpoint, risk stratification, patient selection, companion diagnostic, predicting response, response to therapy
- **Expanded**: 36 terms (was 10) — added diagnostics, stratification, precision medicine, signature terms
- **Facility screening**: excluded infrastructure sub-projects by title pattern

### Before vs after
| Metric | Before | After |
|--------|--------|-------|
| Total grants | TBD | TBD |
| EXPLICIT_BIOMARKER=TRUE | TBD | TBD |
| Facility excluded | N/A | TBD |

(Fill in actual numbers after Task 4)
EOF
)"
```
