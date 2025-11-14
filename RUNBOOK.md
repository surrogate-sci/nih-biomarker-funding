# NIH Biomarker Funding Analysis - Runbook

## Quick Start (Local Execution)

The Claude Code web environment has network restrictions that prevent downloading large NIH ExPORTER files. To run the complete pipeline locally:

### 1. Clone the Repository

```bash
git clone https://github.com/surrogate-sci/nih-biomarker-funding.git
cd nih-biomarker-funding
git checkout claude/filter-sciop-dataset-markers-01FiwEUXU4tCTQTmoMszq31w
```

### 2. Install Dependencies

```bash
pip install pandas requests
```

### 3. Process NIH ExPORTER Data (2020-2024)

```bash
# Download and filter all fiscal years 2020-2024
python3 scripts/process_all_years.py --start-year 2020 --end-year 2024

# Or with verbose output:
python3 scripts/process_all_years.py --start-year 2020 --end-year 2024 --verbose
```

This will:
- Download ZIP files from NIH ExPORTER (~200-300MB each)
- Extract the project CSV files
- Filter each year for biomarker-related projects (11 search terms)
- Combine results into `data/filtered/biomarker_2020-2024.csv`
- Generate `data/filtered/PROCESSING_REPORT.md` with statistics

**Expected Output:**
- Raw downloads: ~1.5 GB (5 years × ~300MB each)
- Filtered output: ~50-150 MB combined
- Processing time: ~15-30 minutes (depending on connection speed)

### 4. Review Results

```bash
# View processing report
cat data/filtered/PROCESSING_REPORT.md

# Quick statistics
wc -l data/filtered/biomarker_2020-2024.csv
head -20 data/filtered/biomarker_2020-2024.csv
```

### 5. Calculate Total Funding by Project

```python
import pandas as pd

# Load combined dataset
df = pd.read_csv('data/filtered/biomarker_2020-2024.csv')

# Total funding per project across all years
project_totals = df.groupby('CORE_PROJECT_NUM').agg({
    'TOTAL_COST': 'sum',
    'PROJECT_TITLE': 'first',
    'ORG_NAME': 'first'
}).reset_index()

project_totals = project_totals.sort_values('TOTAL_COST', ascending=False)

print(f"Total projects: {len(project_totals)}")
print(f"Total funding: ${project_totals['TOTAL_COST'].sum():,.0f}")
print("\nTop 10 projects by funding:")
print(project_totals.head(10))
```

## Alternative: Process Specific Fiscal Years

### Download and Filter One Year

```bash
# FY2023 only
python3 scripts/filter_biomarker_projects.py \
  --download-url https://exporter.nih.gov/CSVs/final/RePORTER_PRJ_C_FY2023.zip \
  --output data/filtered/biomarker_2023.csv
```

### Filter Existing CSV Files

If you've already downloaded NIH ExPORTER files manually:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv \
  --output data/filtered/biomarker_2023.csv \
  --verbose
```

### Custom Search Terms

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv \
  --terms "biomarker" "diagnostic" "prognostic marker" \
  --output data/filtered/custom_2023.csv
```

## Default Search Configuration

**11 Biomarker Search Terms (OR logic):**
1. clinical marker
2. biomarker
3. surrogate endpoint
4. intermediate outcome
5. endpoints
6. endophenotype
7. genetic marker
8. genomics
9. omics (catches proteomics, metabolomics, etc.)
10. imaging
11. imaging marker

**Search Columns (OR logic):**
- PROJECT_TITLE
- PROJECT_TERMS
- ABSTRACT_TEXT

**Deduplication:**
- Key: (APPLICATION_ID, FY)
- Preserves yearly funding records for multi-year projects

## Understanding the Data

### Multi-Year Projects

NIH ExPORTER provides one CSV file per fiscal year. Multi-year projects appear once per fiscal year file with:
- Different APPLICATION_ID each year (e.g., `10001234`, `10001234-A1`, `10001234-A2`)
- Same CORE_PROJECT_NUM across all years (e.g., `R01AG123456`)
- TOTAL_COST = annual funding for that FY (NOT cumulative)

**Example:** Alzheimer's biomarker project, 2021-2023
```
FY2021: APPLICATION_ID=10001234    CORE_PROJECT_NUM=R01AG123456  TOTAL_COST=$450,000
FY2022: APPLICATION_ID=10001234-A1 CORE_PROJECT_NUM=R01AG123456  TOTAL_COST=$480,000
FY2023: APPLICATION_ID=10001234-A2 CORE_PROJECT_NUM=R01AG123456  TOTAL_COST=$500,000

Total project funding = $1,430,000 (sum of all years)
```

### Key Data Fields

- **APPLICATION_ID**: Unique per fiscal year award
- **CORE_PROJECT_NUM**: Stable project identifier across years
- **FY**: Fiscal year
- **TOTAL_COST**: Annual funding amount
- **PROJECT_TITLE**: Project title
- **PROJECT_TERMS**: Keywords/MeSH terms
- **ABSTRACT_TEXT**: Project abstract
- **PHR**: Public health relevance statement
- **ORG_NAME**: Organization name
- **IC_NAME**: NIH institute/center

## File Structure

```
nih-biomarker-funding/
├── scripts/
│   ├── filter_biomarker_projects.py    # Single-year filter script
│   ├── process_all_years.py             # Batch processor for multiple years
│   ├── README.md                        # Usage documentation
│   └── TEST_RESULTS.md                  # Validation results
├── data/
│   ├── raw/                             # Downloaded NIH files (git-ignored)
│   ├── filtered/                        # Filtered biomarker datasets
│   │   ├── biomarker_2020-2024.csv
│   │   └── PROCESSING_REPORT.md
│   ├── test/                            # Test fixtures
│   └── oct-2024/                        # Old partial export (incomplete)
├── .agents/
│   ├── CLAUDE.md                        # Guide for Claude agents
│   └── AGENTS.md                        # Repository guidelines
└── README.md                            # Project overview
```

## Troubleshooting

### Download Failures

If downloads fail (403 Forbidden, network issues):

1. **Manual download:**
   - Visit https://reporter.nih.gov/exporter
   - Download fiscal year ZIP files manually
   - Place in `data/raw/`
   - Run filter script with `--input-csv`

2. **Alternative source (SciOP mirror):**
   - Visit https://sciop.net/datasets/nih-reporter
   - Note: May lag behind official NIH ExPORTER

### Large File Handling

If processing very large CSVs:
- Ensure enough disk space (~5GB for raw + filtered data)
- Use streaming processing (already built into filter script)
- Process one year at a time if memory constrained

### Network Proxy Issues

If behind corporate proxy:
```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
python3 scripts/process_all_years.py --start-year 2020 --end-year 2024
```

## Next Steps

After filtering:

1. **LLM-based classification** (planned)
   - Classify into biomarker research phases
   - Identify contexts of use (diagnostics, trial enrichment, surrogate endpoints)

2. **Aggregation analysis**
   - Roll up by research phase, institute, mechanism, year
   - Export summary tables

3. **Visualization** (optional)
   - Gradio dashboard for interactive exploration

## Support

- Documentation: See `README.md`, `.agents/CLAUDE.md`, and `scripts/README.md`
- Test validation: See `scripts/TEST_RESULTS.md`
- Issues: Check git commit history for implementation details
