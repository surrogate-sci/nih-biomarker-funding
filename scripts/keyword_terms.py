"""
Biomarker keyword term sets, matching logic, and facility screening.

Extracted from filter_biomarker_projects.py so other scripts can import
keyword definitions without pulling in `requests` or other heavy dependencies.
"""

import re
from typing import List


# Biomarker-related search terms (case-insensitive)
# Use '+' for AND conditions (e.g., "clinical+omics" requires both words present)

# Core biomarker terms - definite biomarker use cases
# These terms unambiguously indicate biomarker research
CORE_BIOMARKER_TERMS = [
    # Explicit biomarker/marker language
    "biomarker",
    "clinical marker",
    "surrogate endpoint",
    "imaging marker",
    # Moved from expanded — definite biomarker concepts
    "endophenotype",
    "intermediate outcome",
    "intermediate endpoint",
    "digital endpoint",
    # Biomarker decision-making (from keyword distribution analysis, issue #27)
    "risk stratification",
    "patient selection",
    "companion diagnostic",
    "predicting response",
    "response to therapy",
]

# Expanded biomarker terms - broader coverage, will include false positives
# These capture putative biomarker decision-making grants but are less specific.
# Grants matched only by expanded terms need downstream screening (e.g., LLM grading).
EXPANDED_BIOMARKER_TERMS = [
    # All core terms
    *CORE_BIOMARKER_TERMS,
    # Broader omics/phenotype terms (from original expanded set)
    "digital biomarker",
    "genetic marker",
    "clinical+omics",  # Requires both "clinical" AND "omics"
    "clinical+imaging",  # Requires both "clinical" AND "imaging"
    # Diagnostics and prediction
    "diagnostic accuracy",
    "diagnostic sensitivity",
    "diagnostic specificity",
    "clinical diagnostics",
    "personalized diagnostics",
    "clinical predictors",
    "prognostic value",
    "prognostic assays",
    "clinically actionable",
    # Stratification and heterogeneity
    "patient stratification",
    "disease heterogeneity",
    "disease stratification",
    "clinical subtypes",
    # Precision medicine and signatures
    "theranostics",
    "precision oncology",
    "predictive signature",
    "genomic signature",
    "proteomic signature",
    "biosignature",
]


# Priority order: most specific biomarker concept → most generic
# Used to assign each grant a single PRIMARY_TERM for non-overlapping counts
TERM_PRIORITY = [
    "surrogate endpoint",
    "intermediate outcome",
    "intermediate endpoint",
    "digital endpoint",
    "companion diagnostic",
    "risk stratification",
    "patient selection",
    "predicting response",
    "response to therapy",
    "digital biomarker",
    "imaging marker",
    "clinical marker",
    "endophenotype",
    "genetic marker",
    "diagnostic accuracy",
    "diagnostic sensitivity",
    "diagnostic specificity",
    "clinical diagnostics",
    "personalized diagnostics",
    "clinical predictors",
    "prognostic value",
    "prognostic assays",
    "clinically actionable",
    "patient stratification",
    "disease heterogeneity",
    "disease stratification",
    "clinical subtypes",
    "theranostics",
    "precision oncology",
    "predictive signature",
    "genomic signature",
    "proteomic signature",
    "biosignature",
    "clinical+omics",
    "clinical+imaging",
    "biomarker",
]


# Facility grant screening - exclude infrastructure/admin sub-projects
# These are center components (cores, shared resources) not independent research.
# Note: center grants themselves (P30, P50) ARE often biomarker work.
FACILITY_TITLE_PATTERNS = [
    r"\bAdministrative Core\b",
    r"\bBiostatistics Core\b",
    r"\bBioinformatics Core\b",
    r"\bData Core\b",
    r"\bShared Resource\b",
    r"\bShared Facility\b",
    r"\bInformatics Core\b",
    r"\bStatistics Core\b",
    r"\bBiorepository Core\b",
    r"\bTissue Procurement\b",
    r"\bCore [A-Z]:",  # e.g., "Core C: Biostatistics and Bioinformatics Core"
]


def primary_term(matched_terms: List[str]) -> str:
    """Assign a single primary term from a list of matched terms.

    Uses TERM_PRIORITY ordering: most specific biomarker concept wins.
    Returns empty string if matched_terms is empty.

    Args:
        matched_terms: List of terms that matched (from find_matching_terms or MATCHED_TERMS column)

    Returns:
        The highest-priority term, or "" if no terms provided.
    """
    if not matched_terms:
        return ""
    for term in TERM_PRIORITY:
        if term in matched_terms:
            return term
    # Fallback: return first term if somehow not in priority list
    return matched_terms[0]


def find_matching_terms(text: str, terms: List[str]) -> List[str]:
    """
    Return which biomarker terms match in text (case-insensitive).

    Args:
        text: Text to search
        terms: List of search terms (single terms or AND conditions with '+')

    Returns:
        List of matched terms (empty if none match)
    """
    if not text:
        return []

    text_lower = text.lower()
    matched = []

    for term in terms:
        if "+" in term:
            parts = [part.strip().lower() for part in term.split("+")]
            if all(part in text_lower for part in parts):
                matched.append(term)
        else:
            if term.lower() in text_lower:
                matched.append(term)

    return matched


def contains_biomarker_terms(text: str, terms: List[str]) -> bool:
    """
    Check if text contains any of the biomarker terms (case-insensitive).

    Supports AND conditions using '+' separator (e.g., "clinical+omics" requires both words).

    Args:
        text: Text to search
        terms: List of search terms (single terms or AND conditions with '+')

    Returns:
        True if any term (or AND condition) is found, False otherwise
    """
    if not text:
        return False

    text_lower = text.lower()

    for term in terms:
        if "+" in term:
            # AND condition: all parts must be present
            parts = [part.strip().lower() for part in term.split("+")]
            if all(part in text_lower for part in parts):
                return True
        else:
            # Single term: just check if present
            if term.lower() in text_lower:
                return True

    return False


def is_facility_grant(title: str) -> bool:
    """
    Check if a grant title indicates an infrastructure/facility sub-project.

    These are center components (admin cores, shared resources, data cores)
    rather than independent research. Center grants themselves are NOT excluded.

    Args:
        title: PROJECT_TITLE text

    Returns:
        True if the title matches a facility pattern
    """
    if not title:
        return False
    for pattern in FACILITY_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False
