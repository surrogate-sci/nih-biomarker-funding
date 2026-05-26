#!/usr/bin/env bash
# Run a selective rubric-iteration grading eval via `inspect eval-set`.
#
# Detached via nohup so the run survives session close. Output goes to
# logs/selective-v1/inspect.log; the .eval files for each model land in
# the same directory.
#
# Usage:
#   bash scripts/run-selective.sh
#   bash scripts/run-selective.sh --dataset data/selective_v1_nci.csv
#   bash scripts/run-selective.sh --models google/gemini-2.5-flash-lite,together/openai/gpt-oss-120b
#
# After completion, append a row per model to logs/manifest.csv (Issue #41).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSPECT="$REPO_ROOT/.venv/bin/inspect"
ENV_FILE="$REPO_ROOT/.env"

DATASET="data/selective_v1_nci.csv"
LOG_DIR="logs/selective-v1/"
MODELS="google/gemini-2.5-flash-lite,together/openai/gpt-oss-120b"
TEMPERATURE="0.0"

usage() {
    echo "Usage: $0 [--dataset <path>] [--log-dir <dir>] [--models <m1,m2>] [--temperature <float>]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dataset)     DATASET="$2";     shift 2 ;;
        --log-dir)     LOG_DIR="$2";     shift 2 ;;
        --models)      MODELS="$2";      shift 2 ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        *) usage ;;
    esac
done

if [[ ! -f "$REPO_ROOT/$DATASET" ]]; then
    echo "ERROR: dataset $DATASET not found."
    echo "  Run: python3 scripts/build_selective_sample.py"
    exit 1
fi

mkdir -p "$REPO_ROOT/$LOG_DIR"

if [[ -f "$ENV_FILE" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
else
    echo "WARNING: $ENV_FILE not found — API keys must be set in environment"
fi

LOG_FILE="$REPO_ROOT/$LOG_DIR/inspect.log"
PID_FILE="$REPO_ROOT/$LOG_DIR/inspect.pid"

echo "Starting selective grading eval-set:"
echo "  Models:   $MODELS"
echo "  Dataset:  $DATASET"
echo "  Log dir:  $LOG_DIR"
echo "  Log file: $LOG_FILE"

nohup "$INSPECT" eval-set "$REPO_ROOT/inspect_task.py" \
    --model "$MODELS" \
    -T "dataset_path=$DATASET" \
    --temperature "$TEMPERATURE" \
    --log-dir "$REPO_ROOT/$LOG_DIR" \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo "$PID" > "$PID_FILE"

echo "  PID:      $PID  (saved to $PID_FILE)"
echo ""
echo "Check status:  kill -0 \$(cat $PID_FILE) && echo running || echo done"
echo "Watch output:  tail -f $LOG_FILE"
echo ""
echo "REMINDER: When complete, append a row PER MODEL to logs/manifest.csv (Issue #41)"
