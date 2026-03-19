#!/bin/bash
set -euo pipefail

# Only relevant for remote environments (Claude Code on the web)
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

DATA_DIR="${CLAUDE_PROJECT_DIR}/data"
DATASET_ZIP="nih_biomarker_unified_2004-2024.zip"
DATASET_CSV="nih_biomarker_unified_2004-2024.csv"
DOWNLOAD_URL="https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/${DATASET_ZIP}"

# Only download if data directory is empty or missing the main dataset
if [ -f "${DATA_DIR}/${DATASET_CSV}" ]; then
  exit 0
fi

echo "Data directory missing dataset — downloading from GitHub release..."
mkdir -p "${DATA_DIR}"
curl -L --retry 3 -o "${DATA_DIR}/${DATASET_ZIP}" "${DOWNLOAD_URL}"
unzip -o "${DATA_DIR}/${DATASET_ZIP}" -d "${DATA_DIR}/"
rm -f "${DATA_DIR}/${DATASET_ZIP}"
echo "Dataset downloaded: ${DATA_DIR}/${DATASET_CSV}"

# Install Python dependencies if requirements.txt exists
if [ -f "${CLAUDE_PROJECT_DIR}/requirements.txt" ]; then
  pip install -q -r "${CLAUDE_PROJECT_DIR}/requirements.txt"
fi
