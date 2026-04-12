#!/usr/bin/env bash
# Download the NIH biomarker unified dataset from the GitHub release.
# Tries gh CLI first (authenticated), falls back to curl.
# Idempotent — skips if dataset already exists.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$REPO_ROOT/data"
CSV_FILE="$DATA_DIR/nih_biomarker_unified_2004-2024.csv"
ZIP_FILE="$DATA_DIR/nih_biomarker_unified_2004-2024.zip"
REPO="surrogate-sci/nih-biomarker-funding"
TAG="dataset-release-v3.1"
EXPECTED_SHA="899e8e20f3f5a44d30dacc932cf39b1b7960484999c1db13ed3c10ff1b662b5b"

PILOT_FILE="$DATA_DIR/pilot_sample_12IC_tiered_seed42.csv"
PILOT_SHA="3db257e5776bdf35176837e0dc4d2edb29d736e9845362b78d67b49b86add6c6"

NCI_FILE="$DATA_DIR/nci_sample_v31_seed42.csv"
NCI_SHA="<TO_BE_FILLED_AFTER_UPLOAD>"

if [ -f "$CSV_FILE" ] && [ -f "$PILOT_FILE" ] && [ -f "$NCI_FILE" ]; then
    echo "All dataset files present, skipping download."
    exit 0
fi

mkdir -p "$DATA_DIR"

# Try gh CLI first (handles auth for private repos)
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
    echo "Downloading dataset via gh CLI..."
    gh release download "$TAG" --repo "$REPO" --dir "$DATA_DIR" --pattern "*.zip"
elif [ -n "${GITHUB_TOKEN:-}" ]; then
    echo "Downloading dataset via curl with GITHUB_TOKEN..."
    curl -L -H "Authorization: token $GITHUB_TOKEN" \
        -o "$ZIP_FILE" \
        "https://github.com/$REPO/releases/download/$TAG/nih_biomarker_unified_2004-2024.zip"
else
    echo "Downloading dataset via curl (requires public repo or unrestricted internet)..."
    curl -L -o "$ZIP_FILE" \
        "https://github.com/$REPO/releases/download/$TAG/nih_biomarker_unified_2004-2024.zip"
fi

if [ -f "$ZIP_FILE" ]; then
    echo "Unzipping..."
    unzip -o "$ZIP_FILE" -d "$DATA_DIR/"
    rm -f "$ZIP_FILE"
fi

if [ -f "$CSV_FILE" ]; then
    ACTUAL_SHA=$(shasum -a 256 "$CSV_FILE" 2>/dev/null || sha256sum "$CSV_FILE" 2>/dev/null)
    ACTUAL_SHA="${ACTUAL_SHA%% *}"
    if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
        echo "ERROR: SHA256 mismatch!"
        echo "  Expected: $EXPECTED_SHA"
        echo "  Got:      $ACTUAL_SHA"
        echo "  Update EXPECTED_SHA in this script if the dataset was intentionally changed."
        exit 1
    fi
    echo "Dataset ready: $(wc -l < "$CSV_FILE") rows, SHA256 verified."
else
    echo "ERROR: Dataset download failed. Options:"
    echo "  1. Set GITHUB_TOKEN env var and retry"
    echo "  2. Run 'gh auth login' and retry"
    echo "  3. Download manually from GitHub releases and place in $DATA_DIR/"
    exit 1
fi

# Download pilot sample if not already present
if [ ! -f "$PILOT_FILE" ]; then
    echo "Downloading pilot sample..."
    if command -v gh &>/dev/null && gh auth status &>/dev/null; then
        gh release download "$TAG" --repo "$REPO" --dir "$DATA_DIR" --pattern "pilot_sample_12IC_tiered_seed42.csv"
    elif [ -n "${GITHUB_TOKEN:-}" ]; then
        curl -L -H "Authorization: token $GITHUB_TOKEN" \
            -o "$PILOT_FILE" \
            "https://github.com/$REPO/releases/download/$TAG/pilot_sample_12IC_tiered_seed42.csv"
    else
        curl -L -o "$PILOT_FILE" \
            "https://github.com/$REPO/releases/download/$TAG/pilot_sample_12IC_tiered_seed42.csv"
    fi
fi

if [ -f "$PILOT_FILE" ]; then
    ACTUAL_PILOT_SHA=$(shasum -a 256 "$PILOT_FILE" 2>/dev/null || sha256sum "$PILOT_FILE" 2>/dev/null)
    ACTUAL_PILOT_SHA="${ACTUAL_PILOT_SHA%% *}"
    if [ "$ACTUAL_PILOT_SHA" != "$PILOT_SHA" ]; then
        echo "ERROR: Pilot sample SHA256 mismatch!"
        echo "  Expected: $PILOT_SHA"
        echo "  Got:      $ACTUAL_PILOT_SHA"
        echo "  Update PILOT_SHA in this script if the pilot sample was intentionally changed."
        exit 1
    fi
    echo "Pilot sample ready: $(wc -l < "$PILOT_FILE") rows, SHA256 verified."
else
    echo "ERROR: Pilot sample download failed. Options:"
    echo "  1. Set GITHUB_TOKEN env var and retry"
    echo "  2. Run 'gh auth login' and retry"
    echo "  3. Download manually from GitHub releases and place in $DATA_DIR/"
    exit 1
fi

# Download NCI sample if not already present
if [ ! -f "$NCI_FILE" ]; then
    echo "Downloading NCI sample..."
    if command -v gh &>/dev/null && gh auth status &>/dev/null; then
        gh release download "$TAG" --repo "$REPO" --dir "$DATA_DIR" --pattern "nci_sample_v31_seed42.csv"
    elif [ -n "${GITHUB_TOKEN:-}" ]; then
        curl -L -H "Authorization: token $GITHUB_TOKEN" \
            -o "$NCI_FILE" \
            "https://github.com/$REPO/releases/download/$TAG/nci_sample_v31_seed42.csv"
    else
        curl -L -o "$NCI_FILE" \
            "https://github.com/$REPO/releases/download/$TAG/nci_sample_v31_seed42.csv"
    fi
fi

if [ -f "$NCI_FILE" ]; then
    ACTUAL_NCI_SHA=$(shasum -a 256 "$NCI_FILE" 2>/dev/null || sha256sum "$NCI_FILE" 2>/dev/null)
    ACTUAL_NCI_SHA="${ACTUAL_NCI_SHA%% *}"
    if [ "$ACTUAL_NCI_SHA" != "$NCI_SHA" ]; then
        echo "ERROR: NCI sample SHA256 mismatch!"
        echo "  Expected: $NCI_SHA"
        echo "  Got:      $ACTUAL_NCI_SHA"
        echo "  Update NCI_SHA in this script if the NCI sample was intentionally changed."
        exit 1
    fi
    echo "NCI sample ready: $(wc -l < "$NCI_FILE") rows, SHA256 verified."
else
    echo "ERROR: NCI sample download failed. Options:"
    echo "  1. Set GITHUB_TOKEN env var and retry"
    echo "  2. Run 'gh auth login' and retry"
    echo "  3. Download manually from GitHub releases and place in $DATA_DIR/"
    exit 1
fi
