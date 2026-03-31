"""
Biomarker keyword term sets and matching logic.

Extracted from filter_biomarker_projects.py so other scripts can import
keyword definitions without pulling in `requests` or other heavy dependencies.
"""

from typing import List


# Biomarker-related search terms (case-insensitive)
# Use '+' for AND conditions (e.g., "clinical+omics" requires both words present)

# Core biomarker terms - high confidence, explicit biomarker language
CORE_BIOMARKER_TERMS = [
    "biomarker",
    "clinical marker",
    "surrogate endpoint",
    "imaging marker",
]

# Expanded biomarker terms - broader coverage including omics and phenotypes
EXPANDED_BIOMARKER_TERMS = [
    "clinical marker",
    "biomarker",
    "digital biomarker",
    "surrogate endpoint",
    "intermediate outcome",
    "endophenotype",
    "genetic marker",
    "clinical+omics",  # Requires both "clinical" AND "omics"
    "clinical+imaging",  # Requires both "clinical" AND "imaging"
    "imaging marker",
]


# Priority order: most specific biomarker concept → most generic
# Used to assign each grant a single PRIMARY_TERM for non-overlapping counts
TERM_PRIORITY = [
    "surrogate endpoint",
    "intermediate outcome",
    "digital biomarker",
    "imaging marker",
    "clinical marker",
    "endophenotype",
    "genetic marker",
    "clinical+omics",
    "clinical+imaging",
    "biomarker",
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
        if '+' in term:
            parts = [part.strip().lower() for part in term.split('+')]
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
        if '+' in term:
            # AND condition: all parts must be present
            parts = [part.strip().lower() for part in term.split('+')]
            if all(part in text_lower for part in parts):
                return True
        else:
            # Single term: just check if present
            if term.lower() in text_lower:
                return True

    return False
