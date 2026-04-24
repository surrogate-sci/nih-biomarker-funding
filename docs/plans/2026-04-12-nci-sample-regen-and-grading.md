# NCI Sample Regeneration + Grading Re-run Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix `not_applicable` rubric definition, add TDD test cases for the boundary, implement P30 activity-code filter in the sampler, regenerate the NCI sample, remove it from git, and re-run grading with both models (no `--batch`).

**Architecture:** Five independent concerns addressed in dependency order: (1) rubric + test cases, (2) sampler filter, (3) NCI sample regeneration + release upload, (4) inspect test suite fix, (5) grading re-run. Tasks 1–2 can be committed independently. Task 3 depends on task 2. Task 5 depends on task 3.

**Tech Stack:** Python 3.11 (venv at `.venv/`), Inspect AI 0.3.205 (`.venv/bin/inspect`), `gh` CLI at `/opt/homebrew/bin/gh`, `unittest` for tests.

**Run all tests with:**
```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_sample_grants tests.test_inspect_task -v
```

---

## Task 1: Update `not_applicable` in RUBRIC.md

**Files:**
- Modify: `data/RUBRIC.md`

**Context:** The current `not_applicable` definition does not distinguish between grants that *provide support for* biomarker studies (specimen banks, coordinating centers, data repositories) versus grants that *conduct* biomarker research themselves — including technology or measurement development for biomarker development.

**Step 1: Locate the `not_applicable` entry**

In `data/RUBRIC.md`, find this paragraph (currently at the end of the Dimension 1 code list):

```
**`not_applicable`** — Assign when the grant matched keyword screening but is not substantively about biomarker research. Examples: satellite or administrative cores, infrastructure supplements, cost-effectiveness or health policy analyses, cohort recruitment infrastructure without biomarker measurement or validation as a primary aim. When assigned, Dimension 2 and Dimension 3 are null — do not assign codes for research design or evidence strength.
```

**Step 2: Replace with expanded definition**

Replace the paragraph above with:

```
**`not_applicable`** — Assign when the grant matched keyword screening but is not substantively about biomarker research. Examples: satellite or administrative cores, infrastructure supplements, cost-effectiveness or health policy analyses, cohort recruitment infrastructure without biomarker measurement or validation as a primary aim.

The key distinction is whether the grant is *providing support for* biomarker studies versus *conducting* them. Grants whose primary purpose is specimen banking, data distribution, coordinating infrastructure, or administrative management of a network — where the biomarker work is done by other investigators using the resources — assign `not_applicable`. Grants that conduct actual biomarker research, including technology or measurement development to develop or validate biomarkers (e.g., developing and validating quantitative imaging methods as biomarkers, even when funded through a shared-resource mechanism), do NOT assign `not_applicable`.

When assigned, Dimension 2 and Dimension 3 are null — do not assign codes for research design or evidence strength.
```

**Step 3: Verify code count is unchanged**

`not_applicable` was already in the list — this is an edit to an existing definition, not a new code. No count changes.

**Step 4: Run existing inspect tests to confirm RUBRIC.md still parses**

```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_inspect_task.TestCodeEnums -v
```

Expected: existing Dim1 count test (17 codes) still passes.

**Step 5: Commit**

```bash
git add data/RUBRIC.md
git commit -m "rubric: sharpen not_applicable — support-for vs conducting biomarker research"
```

---

## Task 2: Add TDD test cases for `not_applicable` boundary

**Files:**
- Modify: `data/grader_calibration_examples.csv`

**Context:** These are internal development test cases for agentic rubric checking (TDD), not gold labels for external benchmarks. Manjari sets gold labels only when explicitly flagging them. The cases below establish the `not_applicable` boundary validated during the 2026-04-12 session.

The calibration CSV columns are: `YEAR, APPLICATION_ID, ADMINISTERING_IC, ACTIVITY, TOTAL_COST, PROJECT_TITLE, ABSTRACT_TEXT, MATCHED_TERMS`

Gold-label columns (`GOLD_DIM1`, `GOLD_DIM2`, `GOLD_DIM3`) are supported by `record_to_sample()` and are added here for TDD purposes.

**Step 1: Fetch abstracts for the two boundary cases**

WashU Co-Clinical Imaging (app_id 9296276, FY2017, CA) and NRG Oncology Biospecimen Bank (app_id 8912013, FY2015, CA). Load from RePORTER zip files:

```python
import csv, zipfile, io
from pathlib import Path

targets = {"9296276": "FY2017", "8912013": "FY2015"}
abs_dir = Path.home() / "Downloads"
abstracts = {}
for fy in [2015, 2017]:
    zpath = abs_dir / f"RePORTER_PRJABS_C_FY{fy}.zip"
    with zipfile.ZipFile(zpath) as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                with zf.open(name) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                    for row in reader:
                        if row.get("APPLICATION_ID","").strip() in targets:
                            abstracts[row["APPLICATION_ID"].strip()] = row.get("ABSTRACT_TEXT","").strip()
print(abstracts.keys())
```

**Step 2: Append two rows to `data/grader_calibration_examples.csv`**

Append (do not overwrite) the following rows. `GOLD_DIM1` is the ground truth label established in the 2026-04-12 session.

Row 1 — biospecimen bank, `not_applicable`:
```
2015,8912013,CA,U24,,NRG Oncology Biospecimen Bank,<abstract from step 1>,response to therapy,not_applicable,,
```

Row 2 — imaging biomarker development, NOT `not_applicable`:
```
2017,9296276,CA,U24,,WASHINGTON UNIVERSITY CO-CLINICAL IMAGING RESEARCH RESOURCE,<abstract from step 1>,biomarker;predicting response;response to therapy,predictive_enrichment,,
```

The column order must match the existing CSV header. Add `GOLD_DIM1`, `GOLD_DIM2`, `GOLD_DIM3` columns to the header if not already present (check first).

**Step 3: Verify the rows load correctly via `record_to_sample`**

```python
from inspect_task import record_to_sample
import csv, json

with open("data/grader_calibration_examples.csv") as f:
    rows = list(csv.DictReader(f))

# Check the last two rows
for row in rows[-2:]:
    sample = record_to_sample(row)
    target = json.loads(sample.target) if sample.target else {}
    print(f"{row['APPLICATION_ID']}: target={target}, input_len={len(sample.input)}")
```

Expected: both rows parse, the NRG row has `target={"dim1": "not_applicable"}`, the WashU row has `target={"dim1": "predictive_enrichment"}`.

**Step 4: Commit**

```bash
git add -f data/grader_calibration_examples.csv
git commit -m "data: add TDD boundary cases for not_applicable (NRG bank, WashU imaging)"
```

---

## Task 3: Fix `test_inspect_task.py` — convert to unittest.TestCase

**Files:**
- Modify: `tests/test_inspect_task.py`

**Context:** The test classes use pytest-style (no `TestCase` inheritance, bare `assert` statements). `python3 -m unittest` finds 0 tests. All classes must inherit from `unittest.TestCase` and use `self.assert*` methods.

**Step 1: Verify the problem**

```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_inspect_task -v
```

Expected output: `Ran 0 tests in 0.000s`

**Step 2: Convert all test classes**

For each class in `tests/test_inspect_task.py`:
1. Add `unittest.TestCase` as the base class: `class TestFoo(unittest.TestCase):`
2. Add `import unittest` at the top
3. Replace bare `assert x == y` → `self.assertEqual(x, y)`
4. Replace bare `assert x is None` → `self.assertIsNone(x)`
5. Replace bare `assert x is not None` → `self.assertIsNotNone(x)`
6. Replace bare `assert x in y` → `self.assertIn(x, y)`
7. Replace bare `assert x` → `self.assertTrue(x)`
8. Add `if __name__ == "__main__": unittest.main()` at the bottom

Example conversion for `TestCodeEnums.test_dim1_count`:
```python
# Before
def test_dim1_count(self):
    assert len(VALID_DIM1) == 17

# After
def test_dim1_count(self):
    self.assertEqual(len(VALID_DIM1), 17)
```

**Step 3: Run all tests**

```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_inspect_task -v
```

Expected: all existing tests pass (count matches before conversion).

**Step 4: Commit**

```bash
git add tests/test_inspect_task.py
git commit -m "test: convert test_inspect_task to unittest.TestCase — was finding 0 tests"
```

---

## Task 4: Revert `sample_grants.py` + commit `analyze_eval_results.py`

**Files:**
- Modify: `scripts/sample_grants.py` (revert)
- Commit: `scripts/analyze_eval_results.py`

**Context:** The prior session added `--exclude-activities` and `--rate-multiplier` to `sample_grants.py` without a proper spec. These are context-rotted changes that will be replaced by the correct P30 filter in Task 5. `analyze_eval_results.py` is a working new script that reads journal-based `.eval` ZIP archives and should be committed.

**Step 1: Verify the uncommitted changes**

```bash
git diff scripts/sample_grants.py | head -20
git status scripts/analyze_eval_results.py
```

**Step 2: Revert `sample_grants.py`**

```bash
git checkout HEAD -- scripts/sample_grants.py
```

**Step 3: Verify tests still pass**

```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_sample_grants -v
```

Expected: all tests pass.

**Step 4: Commit `analyze_eval_results.py`**

```bash
git add scripts/analyze_eval_results.py
git commit -m "analysis: add eval results reader for journal-based .eval ZIP archives"
```

---

## Task 5: Implement P30 filter in `load_grants`

**Files:**
- Modify: `scripts/sample_grants.py`
- Modify: `tests/test_sample_grants.py`

**Context:** Filter out P30 grants (Cancer Center Core Grants — infrastructure) unless `NIH_SPENDING_CATS` contains "clinical". All other activity codes pass through unchanged. The unified dataset has a `NIH_SPENDING_CATS` column. Early-year grants (pre-~2008) often have empty spending cats — P30 grants with empty cats are filtered.

**Step 1: Write failing tests first**

Add a new test class to `tests/test_sample_grants.py`:

```python
class TestLoadGrantsP30Filter(unittest.TestCase):
    """Tests for P30 exclusion logic in load_grants."""

    def _make_csv(self, rows: list[dict], path: Path) -> None:
        """Write rows to a temp CSV with all required columns."""
        fieldnames = ["APPLICATION_ID", "FY", "ADMINISTERING_IC", "ACTIVITY",
                      "NIH_SPENDING_CATS", "PROJECT_TITLE", "TOTAL_COST",
                      "EXPLICIT_BIOMARKER", "MATCH_SOURCE"]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({**{k: "" for k in fieldnames}, **row})

    def setUp(self):
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        self.tmp.close()
        self.csv_path = Path(self.tmp.name)

    def tearDown(self):
        self.csv_path.unlink(missing_ok=True)

    def test_p30_without_clinical_is_filtered(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "1", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P30", "NIH_SPENDING_CATS": "Cancer;Basic Science"},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 0)

    def test_p30_with_clinical_is_kept(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "2", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P30", "NIH_SPENDING_CATS": "Clinical Research;Cancer"},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 1)

    def test_p30_empty_spending_cats_is_filtered(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "3", "FY": "2004", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P30", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 0)

    def test_r01_always_kept(self):
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "4", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "R01", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 1)

    def test_p01_always_kept(self):
        """Other P-mechanism grants (P01, P20, P50) are NOT filtered."""
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "5", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P01", "NIH_SPENDING_CATS": "Basic Science"},
            {"APPLICATION_ID": "6", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "P50", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 2)

    def test_u54_always_kept(self):
        """U grants are not filtered regardless of spending cats."""
        from scripts.sample_grants import load_grants
        self._make_csv([
            {"APPLICATION_ID": "7", "FY": "2020", "ADMINISTERING_IC": "CA",
             "ACTIVITY": "U54", "NIH_SPENDING_CATS": ""},
        ], self.csv_path)
        result = load_grants(self.csv_path, ["CA"])
        self.assertEqual(len(result), 1)
```

Also add `import csv` to the test file's imports if not already present.

**Step 2: Run tests — verify they fail**

```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_sample_grants.TestLoadGrantsP30Filter -v
```

Expected: all 6 tests FAIL (ImportError or wrong count).

**Step 3: Implement the filter in `load_grants`**

In `scripts/sample_grants.py`, update the `load_grants` function. The only change is inside the per-row loop — add a P30 check after the IC filter:

```python
def load_grants(csv_path: Path, ics: list[str]) -> list[dict]:
    """Load unified dataset and filter to specified ICs.

    P30 grants (Cancer Center Core Grants) are excluded unless
    NIH_SPENDING_CATS contains 'clinical'.
    """
    ic_set = set(ics)
    rows = []
    n_p30_excluded = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("ADMINISTERING_IC", "").strip() not in ic_set:
                continue
            if row.get("ACTIVITY", "").strip() == "P30":
                spending_cats = row.get("NIH_SPENDING_CATS", "").lower()
                if "clinical" not in spending_cats:
                    n_p30_excluded += 1
                    continue
            rows.append(row)
    if n_p30_excluded:
        print(f"  Excluded {n_p30_excluded:,} P30 grants without clinical spending category")
    return rows
```

Note: this restores the original `load_grants` signature (no `exclude_activities` parameter — that was the context-rotted addition).

**Step 4: Run tests — verify they pass**

```bash
VENV=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/python
$VENV -m unittest tests.test_sample_grants -v
```

Expected: all tests pass including the 6 new P30 filter tests.

**Step 5: Dry-run on the actual dataset to check count**

```bash
python3 scripts/sample_grants.py \
    --unified data/nih_biomarker_unified_2004-2024.csv \
    --ics CA --seed 42 --dry-run
```

Expected output includes a line like `Excluded N P30 grants without clinical spending category`. Note the final pool size and sampled count.

**Step 6: Commit**

```bash
git add scripts/sample_grants.py tests/test_sample_grants.py
git commit -m "sample: filter P30 grants without clinical spending category before sampling"
```

---

## Task 6: Remove NCI sample from git + update `download-dataset.sh`

**Files:**
- Remove from tracking: `data/nci_sample_v31_seed42.csv`
- Modify: `scripts/download-dataset.sh`

**Context:** The NCI sample was force-added to git (`git add -f`) but should live on the GitHub release like the pilot sample, not in git. The file is gitignored; we're removing the tracking exception.

**Step 1: Remove from git tracking**

```bash
git rm --cached data/nci_sample_v31_seed42.csv
```

The file stays on disk — only the git tracking is removed.

**Step 2: Commit the removal**

```bash
git commit -m "data: remove nci_sample from git tracking — will live on release"
```

**Step 3: Add NCI sample download to `download-dataset.sh`**

In `scripts/download-dataset.sh`, after the existing pilot sample download block, add a parallel block for the NCI sample. The SHA256 will be filled in after the file is regenerated and uploaded (Task 8). Add a placeholder for now:

```bash
NCI_FILE="$DATA_DIR/nci_sample_v31_seed42.csv"
NCI_SHA="<TO_BE_FILLED_AFTER_UPLOAD>"

if [ ! -f "$NCI_FILE" ]; then
    echo "Downloading NCI sample..."
    gh release download "$TAG" --repo "$REPO" --dir "$DATA_DIR" \
        --pattern "nci_sample_v31_seed42.csv"
    if [ -f "$NCI_FILE" ]; then
        ACTUAL=$(shasum -a 256 "$NCI_FILE" 2>/dev/null || sha256sum "$NCI_FILE")
        ACTUAL="${ACTUAL%% *}"
        if [ "$ACTUAL" != "$NCI_SHA" ]; then
            echo "ERROR: NCI sample SHA256 mismatch"
            exit 1
        fi
        echo "NCI sample ready."
    fi
fi
```

Also update the early-exit check at the top of the script to include `NCI_FILE`:

```bash
if [ -f "$CSV_FILE" ] && [ -f "$PILOT_FILE" ] && [ -f "$NCI_FILE" ]; then
    echo "All dataset files present, skipping download."
    exit 0
fi
```

**Step 4: Commit the download script update (with placeholder SHA)**

```bash
git add scripts/download-dataset.sh
git commit -m "fetch: add nci_sample download to download-dataset.sh (SHA placeholder)"
```

---

## Task 7: Regenerate NCI sample with P30 filter

**Files:**
- Regenerates: `data/nci_sample_v31_seed42.csv` (local only, not committed)

**Context:** The NCI sample is CA-only, seed 42, 5% tiered rate, 50-grant floor per FY stratum. The P30 filter (Task 5) is now active. FY2016 abstracts are missing — skip that year for abstract joining but keep grants.

**Step 1: Run the sampler**

```bash
python3 scripts/sample_grants.py \
    --unified data/nih_biomarker_unified_2004-2024.csv \
    --abs-dir ~/Downloads \
    --ics CA \
    --seed 42 \
    --output data/nci_sample_v31_seed42.csv \
    --skip-years 2016
```

Expected output: prints pool size, rate, sampled count, abstract join stats. Note final row count.

**Step 2: Verify the output**

```bash
python3 - <<'EOF'
import csv
from collections import Counter
with open("data/nci_sample_v31_seed42.csv") as f:
    rows = list(csv.DictReader(f))
acts = Counter(r["ACTIVITY"] for r in rows)
print(f"Total: {len(rows)}")
print("P30:", acts.get("P30", 0))  # Should be small (only clinical ones)
print("R01:", acts.get("R01", 0))
print("Has abstract:", sum(1 for r in rows if r.get("HAS_ABSTRACT") == "True"))
EOF
```

Expected: P30 count is small (only those with "clinical" in spending cats), total is in the ~3,500–4,200 range.

**Step 3: Run `analyze_eval_results.py` smoke test (optional)**

Confirms the script still works on the existing (partial) GPT eval:

```bash
python3 scripts/analyze_eval_results.py logs/nci-v31-gpt-oss-120b/
```

---

## Task 8: Upload NCI sample to release + finalize SHA in download script

**Files:**
- Upload to: GitHub release `dataset-release-v3.1`
- Modify: `scripts/download-dataset.sh`

**Step 1: Upload to release**

```bash
/opt/homebrew/bin/gh release upload dataset-release-v3.1 \
    data/nci_sample_v31_seed42.csv \
    --repo surrogate-sci/nih-biomarker-funding \
    --clobber
```

**Step 2: Compute SHA256**

```bash
shasum -a 256 data/nci_sample_v31_seed42.csv
```

Copy the hash.

**Step 3: Fill in the placeholder SHA in `download-dataset.sh`**

Replace `<TO_BE_FILLED_AFTER_UPLOAD>` with the actual SHA256 from Step 2.

**Step 4: Commit**

```bash
git add scripts/download-dataset.sh
git commit -m "fetch: fill in nci_sample SHA256 after release upload"
```

---

## Task 9: Re-run grading — both models, no `--batch`

**Context:** Both models failed with batch mode. Gemini: `400 INVALID_ARGUMENT` from Gemini batch API (array type in JSON schema). GPT-OSS-120B via Together AI: batch endpoint rejects OpenAI-format JSONL. Both are confirmed working without `--batch` (the partial GPT run, 421 samples, was 100% valid). Run both in background; append manifest rows when done.

**INSPECT path:**
```bash
INSPECT=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/inspect
```

**Step 1: Smoke test — 5 grants each model**

```bash
export $(grep -v '^#' .env | xargs)

$INSPECT eval inspect_task.py \
    --model google/gemini-2.5-flash-lite \
    -T dataset_path=data/nci_sample_v31_seed42.csv \
    --temperature 0.0 --limit 5 \
    --log-dir logs/test-pipeline/

$INSPECT eval inspect_task.py \
    --model together/openai/gpt-oss-120b \
    -T dataset_path=data/nci_sample_v31_seed42.csv \
    --temperature 0.0 --limit 5 \
    --log-dir logs/test-pipeline/
```

Check `valid_json` and `valid_codes` are 100% for both. If either fails, diagnose before proceeding.

**Step 2: Append smoke test rows to `logs/manifest.csv`**

Per CLAUDE.md, append a row after every `inspect eval` call. Schema (Issue #41):
`run_id,timestamp,log_path,status,reason,model,rubric_version,dataset,n_samples,temperature`

Get `run_id` from the `.eval` filename.

**Step 3: Run full NCI grading — Gemini**

```bash
$INSPECT eval inspect_task.py \
    --model google/gemini-2.5-flash-lite \
    -T dataset_path=data/nci_sample_v31_seed42.csv \
    --temperature 0.0 \
    --log-dir logs/nci-v31-gemini-flash-lite/
```

**Step 4: Run full NCI grading — GPT-OSS-120B**

```bash
$INSPECT eval inspect_task.py \
    --model together/openai/gpt-oss-120b \
    -T dataset_path=data/nci_sample_v31_seed42.csv \
    --temperature 0.0 \
    --log-dir logs/nci-v31-gpt-oss-120b/
```

Run Steps 3 and 4 concurrently if resources allow (separate terminals).

**Step 5: When runs complete — check results**

```bash
python3 scripts/analyze_eval_results.py \
    logs/nci-v31-gemini-flash-lite/ \
    logs/nci-v31-gpt-oss-120b/
```

Check: `valid_json` and `valid_codes` are ≥95% for both models. Note `not_applicable` rate and top Dim1 codes.

**Step 6: Append manifest rows for both runs**

Append two rows to `logs/manifest.csv` with status, model, dataset, n_samples completed.

**Step 7: Commit manifest**

```bash
git add -f logs/manifest.csv
git commit -m "grade: NCI v3.1 full run — gemini-flash-lite and gpt-oss-120b, no batch"
```

---

## Summary of commits

| Task | Commit message |
|------|---------------|
| 1 | `rubric: sharpen not_applicable — support-for vs conducting biomarker research` |
| 2 | `data: add TDD boundary cases for not_applicable (NRG bank, WashU imaging)` |
| 3 | `test: convert test_inspect_task to unittest.TestCase — was finding 0 tests` |
| 4a | `analysis: add eval results reader for journal-based .eval ZIP archives` |
| 5 | `sample: filter P30 grants without clinical spending category before sampling` |
| 6a | `data: remove nci_sample from git tracking — will live on release` |
| 6b | `fetch: add nci_sample download to download-dataset.sh (SHA placeholder)` |
| 8 | `fetch: fill in nci_sample SHA256 after release upload` |
| 9 | `grade: NCI v3.1 full run — gemini-flash-lite and gpt-oss-120b, no batch` |
