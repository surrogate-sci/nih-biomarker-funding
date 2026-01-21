#!/usr/bin/env python3
"""
Extract diverse biomarker project examples from FY2024 data for testing classification prompts.

This script reads the abstract file and filtered biomarker file, merges them, and selects
10 diverse examples spanning different biomarker research phases.
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict
import re


def load_abstracts(abstract_file: Path) -> pd.DataFrame:
    """Load the abstract CSV file."""
    print(f"Loading abstracts from {abstract_file.name}...")
    df = pd.read_csv(abstract_file, dtype={'APPLICATION_ID': str}, low_memory=False)
    # Remove quotes from APPLICATION_ID if present
    df['APPLICATION_ID'] = df['APPLICATION_ID'].astype(str).str.strip('"')
    print(f"  Loaded {len(df):,} abstracts")
    return df


def load_filtered_projects(projects_file: Path) -> pd.DataFrame:
    """Load the filtered biomarker projects CSV file."""
    print(f"Loading projects from {projects_file.name}...")
    df = pd.read_csv(projects_file, dtype={'APPLICATION_ID': str}, low_memory=False)
    print(f"  Loaded {len(df):,} projects")
    return df


def select_diverse_examples(df: pd.DataFrame, n_examples: int = 10) -> List[Dict]:
    """
    Select diverse examples based on keywords and patterns.
    
    Strategy:
    1. Technology development (imaging, platform, assay)
    2. Discovery (identify, discover, novel biomarker)
    3. Development (clinical study, evaluate, assess)
    4. Validation (FDA, regulatory, qualify, validate)
    5. Animal models (mouse, rat, animal model)
    6. Imaging biomarkers (MRI, PET, imaging)
    7. Molecular biomarkers (genomic, proteomic, liquid biopsy)
    8. Clinical trials (phase, trial, clinical)
    9. Predictive/prognostic (predict, prognosis, risk)
    10. Surrogate endpoints (surrogate, endpoint)
    """
    
    examples = []
    used_ids = set()
    
    # Define search patterns for different categories
    categories = [
        {
            'name': 'technology_development',
            'keywords': ['platform', 'technology', 'assay development', 'method development', 'novel technology'],
            'max': 1
        },
        {
            'name': 'discovery',
            'keywords': ['discover', 'identify.*biomarker', 'novel biomarker', 'biomarker discovery'],
            'max': 2
        },
        {
            'name': 'development',
            'keywords': ['clinical study', 'evaluate', 'assess.*biomarker', 'biomarker evaluation'],
            'max': 2
        },
        {
            'name': 'validation',
            'keywords': ['FDA', 'regulatory', 'qualify', 'validation.*biomarker', 'BEST'],
            'max': 1
        },
        {
            'name': 'animal_model',
            'keywords': ['animal model', 'mouse model', 'rat model', 'preclinical'],
            'max': 1
        },
        {
            'name': 'imaging',
            'keywords': ['imaging biomarker', 'MRI', 'PET', 'imaging'],
            'max': 2
        },
        {
            'name': 'molecular',
            'keywords': ['genomic', 'proteomic', 'liquid biopsy', 'circulating', 'blood biomarker'],
            'max': 1
        },
        {
            'name': 'clinical_trial',
            'keywords': ['phase.*trial', 'randomized', 'clinical trial'],
            'max': 1
        },
        {
            'name': 'predictive',
            'keywords': ['predictive biomarker', 'prognostic', 'predict.*response'],
            'max': 1
        },
        {
            'name': 'surrogate',
            'keywords': ['surrogate endpoint', 'intermediate endpoint'],
            'max': 1
        }
    ]
    
    # Search in abstract text and project terms
    text_cols = ['ABSTRACT_TEXT', 'PROJECT_TITLE', 'PROJECT_TERMS']
    available_text_cols = [col for col in text_cols if col in df.columns]
    
    print(f"  Searching in columns: {', '.join(available_text_cols)}")
    
    for category in categories:
        if len(examples) >= n_examples:
            break
            
        found = 0
        for idx, row in df.iterrows():
            if len(examples) >= n_examples:
                break
            if found >= category['max']:
                break
                
            app_id = str(row['APPLICATION_ID'])
            if app_id in used_ids:
                continue
            
            # Check if any keyword matches
            text_to_search = ' '.join([
                str(row.get(col, '')) for col in available_text_cols
            ]).lower()
            
            for keyword in category['keywords']:
                pattern = keyword.lower()
                if re.search(pattern, text_to_search, re.IGNORECASE):
                    # Found a match
                    example = {
                        'application_id': app_id,
                        'project_title': str(row.get('PROJECT_TITLE', 'N/A')),
                        'abstract': str(row.get('ABSTRACT_TEXT', 'N/A')),
                        'project_terms': str(row.get('PROJECT_TERMS', 'N/A')),
                        'category': category['name'],
                        'matched_keyword': keyword
                    }
                    examples.append(example)
                    used_ids.add(app_id)
                    found += 1
                    print(f"  Selected {category['name']}: {app_id} (matched: {keyword})")
                    break
    
    # Fill remaining slots with any biomarker projects
    if len(examples) < n_examples:
        print(f"  Filling {n_examples - len(examples)} remaining slots...")
        for idx, row in df.iterrows():
            if len(examples) >= n_examples:
                break
                
            app_id = str(row['APPLICATION_ID'])
            if app_id in used_ids:
                continue
            
            example = {
                'application_id': app_id,
                'project_title': str(row.get('PROJECT_TITLE', 'N/A')),
                'abstract': str(row.get('ABSTRACT_TEXT', 'N/A')),
                'project_terms': str(row.get('PROJECT_TERMS', 'N/A')),
                'category': 'general',
                'matched_keyword': 'any biomarker project'
            }
            examples.append(example)
            used_ids.add(app_id)
            print(f"  Selected general: {app_id}")
    
    return examples


def main():
    """Main function to extract examples."""
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    abstract_file = project_root / "data" / "reporter_test" / "RePORTER_PRJABS_C_FY2024.csv"
    projects_file = project_root / "data" / "filtered" / "biomarker_FY2024.csv"
    output_file = script_dir / "test_examples.json"
    
    # Check files exist
    if not abstract_file.exists():
        print(f"Error: Abstract file not found: {abstract_file}")
        return
    
    if not projects_file.exists():
        print(f"Error: Projects file not found: {projects_file}")
        return
    
    # Load data
    abstracts_df = load_abstracts(abstract_file)
    projects_df = load_filtered_projects(projects_file)
    
    # Merge on APPLICATION_ID
    print("\nMerging abstracts with projects...")
    merged = projects_df.merge(
        abstracts_df,
        on='APPLICATION_ID',
        how='inner',
        suffixes=('', '_abstract')
    )
    print(f"  Merged dataset: {len(merged):,} projects with abstracts")
    
    # Filter to only projects with non-empty abstracts
    merged = merged[merged['ABSTRACT_TEXT'].notna()]
    merged = merged[merged['ABSTRACT_TEXT'].astype(str).str.strip() != '']
    print(f"  Projects with valid abstracts: {len(merged):,}")
    
    # Select diverse examples
    print(f"\nSelecting {10} diverse examples...")
    examples = select_diverse_examples(merged, n_examples=10)
    
    # Save to JSON
    print(f"\nSaving {len(examples)} examples to {output_file.name}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Successfully extracted {len(examples)} examples")
    print(f"  Output: {output_file}")
    
    # Print summary
    print("\nExample categories:")
    for example in examples:
        print(f"  {example['application_id']}: {example['category']} ({example['matched_keyword']})")


if __name__ == "__main__":
    main()


