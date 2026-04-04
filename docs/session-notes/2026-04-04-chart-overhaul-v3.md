# Session: Chart overhaul & data pipeline gap — 2026-04-04

## What we did
Expanded analysis from 3 to 8 charts, added enriched keyword columns to the keyword filter, opened PR #32 and v3.1 release. Then discovered that `supplement_with_abstracts.py` was never updated with the same columns — so 68K abstract-only grants have incomplete data. All charts, the release, and PR #32 are built on this incomplete data. Issue #35 filed.

## Key decisions
1. **Compute MATCHED_TERMS and PRIMARY_TERM during filtering, not post-hoc** — avoids needing PROJECT_TERMS in unified dataset. (Manjari)
2. **Split into MATCHED_CORE_TERMS and MATCHED_EXPANDED_TERMS** — separate columns by tier. (Manjari)
3. **Core panel: 95% threshold, "Other" callout for intermediate endpoints** — don't invent category buckets, show individual terms. (Manjari)
4. **Expanded panel: 3 categories only** — clinical+omics, clinical+imaging, Other precision medicine terms. (Manjari)
5. **All chart text must be full sentences.** (Manjari)

## Corrections received
- **Don't strip data needed for analysis** → compute derivatives during filtering
- **PRIMARY_TERM must cover all grants** → not just title-matched
- **Scripts must be reproducible** → no ad-hoc bash
- **Don't invent category buckets** → show individual terms with "Other"
- **Don't paste API tokens in tool calls**
- **Don't commit directly to main** → PRs only for code/data changes
- **Both filter scripts must stay in sync** → `supplement_with_abstracts.py` is a parallel path into the same unified dataset; any column change to keyword filter must be mirrored. This was not done.
- **Read the existing plans before acting** → the `2026-04-03-rerun-biomarker-filtering.md` plan covers all 7 tasks including abstract re-filtering. Executing ad-hoc instead of following the plan caused the gap.

## Data pipeline gap (issue #35)

The keyword filter was updated with enriched columns. The abstract filter was not. Downstream consequences:

- **68K abstract-only rows**: empty MATCHED_CORE_TERMS, MATCHED_EXPANDED_TERMS; PRIMARY_TERM patched at load time only
- **v3.1 release**: published with incomplete data
- **11 Datawrapper charts**: published with incomplete data
- **PR #32**: claims 30 uniform columns but 20% of rows have empty keyword columns
- **funding_analysis.json, SUMMARY.md**: per-keyword breakdowns suspect for abstract portion
- **Main repo data/**: still has stale Mar 31 data (332K rows), worktree has incomplete Apr 4 data (344K rows)
- **utils.py load_dataset()**: patches PRIMARY_TERM at load time — masks the source problem

Aggregate figures ($175B total, $62B core, $113B expanded) are probably correct since they use EXPLICIT_BIOMARKER and TOTAL_COST which are populated. Per-keyword breakdowns are affected.

## Next steps
- Fix `supplement_with_abstracts.py` to compute all enriched columns (issue #35)
- Re-run abstract filter, regenerate unified dataset
- Verify all 344K rows have uniform columns before releasing
- Replace v3.1 release, republish Datawrapper charts
- Sync main repo data/ with verified data
- PR #32 blocked until data is fixed

## Files changed this session
- `analysis/biomarker-screening/analyze.py` — 8 charts, core_vs_expanded_terms
- `analysis/biomarker-screening/charts.py` — both renderers, full-sentence labels, threshold logic
- `analysis/biomarker-screening/SUMMARY.md` — all 8 chart sections
- `scripts/filter_biomarker_projects.py` — enriched columns (keyword side only)
- `scripts/create_unified_dataset.py` — COLUMNS_TO_KEEP (30 cols)
- `scripts/process_all_years.py` — keywords/ subdirectory output
- `scripts/download-dataset.sh` — points to v3.1 (needs re-release)
