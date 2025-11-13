# Claude Agent Guide for NIH Biomarker Funding Analysis

## Project Context

This repository analyzes NIH funding patterns for biomarker research across different research phases (technology development, clinical discovery, validation, and qualification). The goal is to quantify spending without relying on brittle keyword-based filters by using permissive initial filtering followed by LLM-based classification.

## Data Structure Understanding

### NIH ExPORTER Data Model

**Key Identifiers:**
- **APPLICATION_ID**: Unique identifier for each fiscal year award of a project
  - Example: `10001234` (FY2021), `10001234-A1` (FY2022), `10001234-A2` (FY2023)
  - Changes annually for the same project

- **CORE_PROJECT_NUM**: Stable identifier across all years of a project
  - Example: `R01AG123456` remains constant across FY2021-2025
  - Use this for multi-year aggregation

- **FY**: Fiscal year (2006-2024)

- **TOTAL_COST**: Annual funding for that specific fiscal year
  - NOT cumulative across years
  - To get total project funding: `SUM(TOTAL_COST) GROUP BY CORE_PROJECT_NUM`

### File Organization

NIH ExPORTER provides separate CSV files per fiscal year:
- `RePORTER_PRJ_C_FY2023.csv` - Projects active in FY2023
- `RePORTER_PRJABS_C_FY2023.csv` - Project abstracts for FY2023
- Each file: ~100-300 MB uncompressed, ~50K-60K projects

**Critical Design Decision:**
Multi-year projects appear once per fiscal year in their respective FY files. To preserve all yearly funding records, our filtering script uses `(APPLICATION_ID, FY)` as the deduplication key, NOT just `APPLICATION_ID`.

## Implementation Decisions

### 1. Filtering Script (`scripts/filter_biomarker_projects.py`)

**Search Strategy:**
- **OR logic** across 11 biomarker terms
- **OR logic** across specified columns (PHR, PROJECT_TITLE, PROJECT_TERMS)
- Case-insensitive substring matching

**Search Terms (as of 2025-11-13):**
1. clinical marker
2. biomarker
3. surrogate endpoint
4. intermediate outcome
5. endpoints
6. endophenotype
7. genetic marker
8. genomics
9. omics (catches proteomics, metabolomics, transcriptomics, etc.)
10. imaging
11. imaging marker

**Deduplication Logic:**
```python
# Composite key preserves yearly funding
unique_key = (APPLICATION_ID, FY)
```

**Why this matters:**
- Example: Alzheimer biomarker project running 2021-2023
  - 3 records kept (one per year)
  - Total funding = $450K + $480K + $500K = $1.43M
- Old logic using only APPLICATION_ID would have kept just 1 record
  - Would undercount funding by ~66%!

### 2. Workflow Philosophy

From `README.md` and `AGENTS.md`:
1. **Ingest** SciOP snapshots with permissive filtering (~50-150 MB/year)
2. **Standardize** dataset structure
3. **Classify** using LLM graders (not yet implemented)
4. **Aggregate** by phase, institute, mechanism, and year
5. **Export** analysis tables

**Data Hygiene:**
- Raw data lives in `data/` (git-ignored)
- Filtered data ~10-50x smaller than raw
- Keep data out of version control

## Common Tasks for Claude Agents

### Task: Filter a Fiscal Year

```bash
# Download from https://reporter.nih.gov/exporter
# Then filter:
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv \
  --output data/filtered/biomarker_projects_2023.csv
```

### Task: Calculate Total Project Funding

After filtering, aggregate in downstream analysis:
```python
import pandas as pd

df = pd.read_csv('data/filtered/biomarker_projects_2020-2024.csv')

# Total funding per project across all years
project_totals = df.groupby('CORE_PROJECT_NUM').agg({
    'TOTAL_COST': 'sum',
    'PROJECT_TITLE': 'first',
    'ORG_NAME': 'first'
}).reset_index()
```

### Task: Combine Multiple Years

When combining fiscal years, ensure preservation of yearly records:
```bash
# Process each year separately
for year in 2020 2021 2022 2023 2024; do
  python3 scripts/filter_biomarker_projects.py \
    --input-csv data/raw/RePORTER_PRJ_C_FY${year}.csv \
    --output data/filtered/biomarker_${year}.csv
done

# Then concatenate (all records preserved)
cat data/filtered/biomarker_*.csv > data/filtered/biomarker_2020-2024.csv
```

## Testing Approach

The project includes test fixtures in `data/test/`:
- `mock_projects.csv` - Single-year test data
- `multi_year_projects.csv` - Multi-year projects to verify funding preservation
- Run: `python3 scripts/filter_biomarker_projects.py --input-csv data/test/multi_year_projects.csv --output data/test/output.csv --verbose`

Verify multi-year funding is preserved:
```bash
# Should show 3 years of funding for Alzheimer project
grep R01AG123456 data/test/output.csv
```

## Key Constraints & Warnings

### What NOT to Do

❌ **Don't deduplicate by CORE_PROJECT_NUM alone** across years
- This would collapse multi-year funding into one record
- Violates the "most unique level of funding spent" requirement

❌ **Don't use APPLICATION_ID alone** for deduplication
- Might work for single-year files
- Breaks when combining multiple fiscal years

❌ **Don't assume TOTAL_COST is cumulative**
- It's annual funding only
- Must sum across FY to get project totals

❌ **Don't commit data files to git**
- They're large (100+ MB)
- Use `.gitignore` for `data/`

### What TO Do

✅ **Use (APPLICATION_ID, FY) for deduplication**
- Preserves yearly funding records
- Enables accurate total funding calculation

✅ **Process one fiscal year file at a time**
- Then combine filtered outputs
- Maintains data lineage

✅ **Document provenance in data/README**
- Record exact download commands
- Note filtering parameters used

✅ **Keep search terms permissive**
- Goal: catch all biomarker-adjacent research
- LLM grading will refine later

## Future Development

According to `AGENTS.md`, upcoming work includes:

1. **LLM-based classification**
   - Classify into biomarker phases
   - Identify contexts of use (diagnostics, clinical trial enrichment, surrogates)
   - Use documented rubric + seeded prompts

2. **Aggregation module**
   - Roll up by research phase, institute, mechanism, year
   - Export analysis tables

3. **Optional dashboard**
   - Gradio-based visualization
   - Interactive exploration of filtered dataset

## Questions to Consider

When implementing new features, ask:

1. **Does this preserve the most granular funding level?**
   - Keep (APPLICATION_ID, FY) records intact

2. **Is the provenance clear?**
   - Can someone reproduce this filtering?
   - Are parameters documented?

3. **Does this scale to 500K+ rows?**
   - Use streaming/chunking for large files
   - Test with realistic data sizes

4. **Is the LLM grading reproducible?**
   - Version prompts
   - Log seeds and temperatures
   - Store grading results with input hashes

## Resources

- NIH ExPORTER: https://reporter.nih.gov/exporter
- ExPORTER Data Dictionary: https://report.nih.gov/exporter-data-dictionary
- SciOP NIH Reporter: https://sciop.net/datasets/nih-reporter
- Understanding NIH Grant Numbers: https://www.era.nih.gov/erahelp/commons/Commons/understandGrantNums.htm

## Version History

- **2025-11-13**: Updated filtering script to preserve multi-year funding records
- **2025-11-13**: Added 4 new search terms (genomics, omics, imaging, imaging marker)
- **2025-11-13**: Initial project structure and documentation

---

**For Questions or Issues:**
- Check `AGENTS.md` for general coding guidelines
- Check `scripts/README.md` for filter script usage
- Check `scripts/TEST_RESULTS.md` for validation tests
