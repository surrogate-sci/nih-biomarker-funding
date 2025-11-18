# NIH Biomarker Funding Analysis - Summary

Generated: 2025-11-18 15:36:10

## Per-Year Results

| Year | Biomarker Relevant Spending | Explicit Biomarker Spending | Matched Projects | Total Scanned |
|------|------------------------------|------------------------------|------------------|---------------|
| 2004 | $1.71B | $0.49B | 6,524 | 65,000 |
| 2005 | $0.11B | $0.06B | 327 | 50,000 |
| 2006 | $0.09B | $0.07B | 336 | 55,000 |
| 2007 | $2.71B | $0.16B | 7,543 | 65,000 |
| 2008 | $2.79B | $0.18B | 8,388 | 70,000 |
| 2009 | $4.80B | $1.60B | 12,722 | 80,000 |
| 2010 | $5.02B | $1.83B | 12,487 | 80,000 |
| 2011 | $4.91B | $1.85B | 12,215 | 80,000 |
| 2012 | $6.51B | $2.51B | 13,628 | 80,000 |
| 2013 | $2.25B | $0.29B | 4,182 | 80,000 |
| 2014 | $5.79B | $0.32B | 11,536 | 80,000 |
| 2015 | $6.10B | $0.48B | 12,189 | 80,000 |
| 2016 | $7.40B | $1.72B | 14,714 | 80,000 |
| 2017 | $8.36B | $2.09B | 16,024 | 73,144 |
| 2018 | $3.87B | $1.09B | 8,435 | 80,826 |
| 2019 | $9.95B | $2.71B | 19,148 | 79,469 |
| 2020 | $11.36B | $3.11B | 20,098 | 82,428 |
| 2021 | $11.54B | $3.33B | 21,001 | 82,940 |
| 2022 | $12.53B | $3.60B | 22,048 | 83,891 |
| 2023 | $13.13B | $4.09B | 22,833 | 85,118 |
| 2024 | $13.55B | $4.19B | 23,252 | 83,501 |

### Column Definitions

- **Year**: NIH fiscal year
- **Biomarker Relevant Spending**: Total TOTAL_COST for all matched projects
- **Explicit Biomarker Spending**: Total TOTAL_COST for projects matching core biomarker terms
- **Matched Projects**: Projects where PROJECT_TITLE or PROJECT_TERMS fields contain any biomarker search term (case-insensitive, with AND logic for terms containing '+')
- **Total Scanned**: Total projects examined in NIH ExPORTER RePORTER_PRJ_C_FY{year}.csv file

### Search Terms Used

**Core biomarker terms (4):**
- biomarker, clinical marker, surrogate endpoint, imaging marker

**Expanded biomarker terms (10):**
- biomarker, clinical marker, surrogate endpoint, imaging marker, digital biomarker, intermediate outcome, endophenotype, genetic marker, clinical+omics, clinical+imaging

## Overall Statistics

### Projects
- **Total Matched Projects (Expanded)**: 269,630
- **Explicit Biomarker Projects (Core)**: 75,849
- **Other Biomarker-Related Projects**: 193,781
- **Total Scanned Projects**: 1,596,317
- **Overall Match Rate**: 16.9%
- **Explicit Biomarker Rate**: 4.8%

### Funding
- **Biomarker Relevant Spending**: $134.49B
- **Explicit Biomarker Spending**: $35.77B (26.6%)

### Processing
- **Years Available**: 21
- **Year Range**: 2004-2024


## Data Structure

- **Deduplication Key**: (APPLICATION_ID, FY)
- **Search Columns**: PROJECT_TITLE, PROJECT_TERMS
- **Search Logic**: OR across all terms, AND logic for terms with '+'
- **Case Sensitivity**: Case-insensitive matching
- **EXPLICIT_BIOMARKER Column**: TRUE for projects matching core terms (biomarker, clinical marker, surrogate endpoint, imaging marker)

## Data Quality Notes

**Known issues with NIH ExPORTER source data:**
- **FY2005**: PROJECT_TERMS field only 68% populated (vs 89% in FY2004)
- **FY2006**: PROJECT_TERMS field completely empty (0% populated)
- Impact: These years show artificially low match counts since matches rely heavily on PROJECT_TERMS keywords
- FY2004, FY2007-2024: PROJECT_TERMS field 86-89% populated (normal)

