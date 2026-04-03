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
TAG="dataset-release-v3.0"

if [ -f "$CSV_FILE" ]; then
    echo "Dataset already present at $CSV_FILE, skipping download."
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
    echo "Dataset ready: $(wc -l < "$CSV_FILE") rows in $CSV_FILE"
else
    echo "ERROR: Dataset download failed. Options:"
    echo "  1. Set GITHUB_TOKEN env var and retry"
    echo "  2. Run 'gh auth login' and retry"
    echo "  3. Download manually from GitHub releases and place in $DATA_DIR/"
    exit 1
fi
