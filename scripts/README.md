# NIH Biomarker Project Filtering Script

## Overview

`filter_biomarker_projects.py` downloads and filters NIH Reporter data from SciOP/ExPORTER to identify biomarker-related research projects based on keyword mentions in project summaries, titles, and terms.

## Features

- **Flexible input**: Filter local CSV files or download directly from URLs
- **Biomarker term detection**: Searches for 7 biomarker-related terms by default
- **Deduplication**: Keeps one row per unique project (by APPLICATION_ID)
- **Progress reporting**: Real-time progress updates for large datasets
- **Retry logic**: Automatic retry with exponential backoff for network issues
- **Memory efficient**: Streams CSV data to handle large files

## Default Search Terms

The script searches for these terms (case-insensitive) by default:

1. **clinical marker**
2. **biomarker**
3. **surrogate endpoint**
4. **intermediate outcome**
5. **endpoints**
6. **endophenotype**
7. **genetic marker**

## Installation

Install required dependencies:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install requests pandas
```

## Data Sources

### SciOP NIH Reporter Dataset

SciOP provides snapshots of NIH Reporter data:
- Website: https://sciop.net/datasets/nih-reporter
- Contains projects, abstracts, publications, and more

### NIH ExPORTER (Official Source)

NIH ExPORTER is the official source for NIH funding data:
- Website: https://reporter.nih.gov/exporter
- CSV files available by fiscal year
- Updated weekly (typically Sunday nights)

### File Structure

NIH ExPORTER provides several CSV files:

- **RePORTER_PRJ_C_FY{YEAR}.csv** - Projects (core dataset)
  - Contains: APPLICATION_ID, PROJECT_TITLE, PHR (public health relevance), PROJECT_TERMS, funding details, etc.

- **RePORTER_PRJABS_C_FY{YEAR}.csv** - Project Abstracts
  - Contains: APPLICATION_ID, ABSTRACT_TEXT

- **RePORTER_PUB_C_{YEAR}.csv** - Publications
- **RePORTER_LINK_{YEAR}.csv** - Project-Publication links
- And others...

## Usage

### Basic Usage - Filter Local File

Filter an existing CSV file:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv \
  --output data/filtered/biomarker_projects_2023.csv
```

### Download and Filter

Download a file and filter it in one step:

```bash
python3 scripts/filter_biomarker_projects.py \
  --download-url https://exporter.nih.gov/CSVs/final/RePORTER_PRJ_C_FY2023.zip \
  --output data/filtered/biomarker_projects_2023.csv
```

### Custom Search Terms

Use your own search terms:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/projects.csv \
  --terms "biomarker" "diagnostic marker" "prognostic marker" \
  --output data/filtered/custom_biomarkers.csv
```

### Search Specific Columns

Specify which columns to search:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/projects.csv \
  --columns PHR PROJECT_TITLE ABSTRACT_TEXT \
  --output data/filtered/biomarkers.csv
```

### Include Abstracts

Filter both projects and their abstracts:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv \
  --abstracts-csv data/raw/RePORTER_PRJABS_C_FY2023.csv \
  --output data/filtered/biomarker_projects_2023.csv \
  --abstracts-output data/filtered/biomarker_abstracts_2023.csv
```

### Verbose Output

Enable detailed logging:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/projects.csv \
  --output filtered.csv \
  --verbose
```

## Command-Line Options

### Input Options (choose one)

- `--input-csv PATH` - Path to local projects CSV file
- `--download-url URL` - URL to download CSV/ZIP file
- `--year YEAR` - Fiscal year (experimental, shows manual download instructions)

### Output Options

- `--output PATH` / `-o PATH` - Output CSV path (default: `data/filtered/biomarker_projects.csv`)
- `--abstracts-output PATH` - Output path for filtered abstracts

### Filtering Options

- `--terms TERM [TERM ...]` - Custom search terms (default: 7 biomarker terms)
- `--columns COL [COL ...]` - Columns to search (default: PHR, PROJECT_TITLE, PROJECT_TERMS)
- `--id-column COL` - Column for deduplication (default: APPLICATION_ID)
- `--abstracts-csv PATH` - Path to abstracts CSV (optional)

### General Options

- `--data-dir PATH` - Directory for downloads (default: `data/raw`)
- `--verbose` / `-v` - Enable verbose logging
- `--help` / `-h` - Show help message

## Workflow Example

### Step 1: Download NIH ExPORTER Data

Visit https://reporter.nih.gov/exporter and download:
- Projects CSV for your fiscal year (e.g., `RePORTER_PRJ_C_FY2023.zip`)
- Abstracts CSV (optional, e.g., `RePORTER_PRJABS_C_FY2023.zip`)

Extract the ZIP files to `data/raw/`:

```bash
mkdir -p data/raw
unzip RePORTER_PRJ_C_FY2023.zip -d data/raw/
unzip RePORTER_PRJABS_C_FY2023.zip -d data/raw/
```

### Step 2: Filter for Biomarker Projects

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/RePORTER_PRJ_C_FY2023.csv \
  --abstracts-csv data/raw/RePORTER_PRJABS_C_FY2023.csv \
  --output data/filtered/biomarker_projects_2023.csv \
  --abstracts-output data/filtered/biomarker_abstracts_2023.csv \
  --verbose
```

### Step 3: Review Results

The filtered CSV will contain only projects with biomarker-related mentions, with one row per unique project ID.

Check the log output for statistics:
- Total rows processed
- Rows matching search terms
- Unique projects kept (after deduplication)
- Duplicates removed

## Output Format

The output CSV maintains the same structure as the input, with all original columns preserved. Projects are deduplicated by the ID column (default: APPLICATION_ID).

### Key Columns in Output

- **APPLICATION_ID** - Unique project identifier
- **PROJECT_TITLE** - Project title
- **PHR** - Public Health Relevance statement
- **PROJECT_TERMS** - Keywords/terms associated with project
- **CORE_PROJECT_NUM** - Core project number (for linking related records)
- **FY** - Fiscal year
- **ORG_NAME** - Organization name
- **TOTAL_COST** - Total project cost
- And all other original columns...

## Data Size Expectations

Based on the project guidelines:
- **Raw data**: 50-150 MB per year/cohort
- **Filtered data**: Much smaller, depending on search terms
- **Example**: FY2023 projects CSV (~500,000 rows) → ~10,000-50,000 biomarker projects (rough estimate)

## Notes

- **Case-insensitive search**: All searches are case-insensitive
- **Deduplication**: Uses APPLICATION_ID by default; change with `--id-column`
- **Missing columns**: Script will use all available columns if specified columns don't exist
- **ZIP files**: Currently requires manual extraction; automatic unzip support coming soon
- **Network retry**: Automatic retry with exponential backoff (2s, 4s, 8s, 16s)

## Troubleshooting

### "Column not found" error

The CSV might use different column names. Check available columns:

```bash
head -1 data/raw/your_file.csv
```

Then specify the correct columns:

```bash
python3 scripts/filter_biomarker_projects.py \
  --input-csv data/raw/your_file.csv \
  --columns ACTUAL_COLUMN_NAME1 ACTUAL_COLUMN_NAME2 \
  --id-column ACTUAL_ID_COLUMN
```

### No matches found

Try:
1. Enable verbose mode to see what's being searched
2. Check if your search terms appear in the specified columns
3. Try searching all columns (the script will auto-detect if specified columns are missing)

### Download fails

NIH ExPORTER URLs may change. If automatic download fails:
1. Manually download from https://reporter.nih.gov/exporter
2. Extract the ZIP file
3. Use `--input-csv` instead of `--download-url`

## Future Enhancements

Planned features:
- [ ] Automatic ZIP file extraction
- [ ] Multi-year batch processing
- [ ] Integration with NIH Reporter API
- [ ] LLM-based project classification (per project goals)
- [ ] Output format options (Parquet, JSON)
- [ ] Fuzzy matching for term variants

## Related Files

- `requirements.txt` - Python dependencies
- `.agents/AGENTS.md` - Project guidelines and workflow
- `README.md` - Project overview

## License

Part of the NIH Biomarker Funding Analysis project.
