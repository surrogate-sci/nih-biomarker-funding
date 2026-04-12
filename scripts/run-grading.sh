#!/usr/bin/env bash
# Run an Inspect AI grading eval detached from the terminal.
#
# The process survives terminal/session close. Output is logged to
# <log-dir>/inspect.log and the PID is saved to <log-dir>/inspect.pid.
#
# Usage:
#   bash scripts/run-grading.sh --model google/gemini-2.5-flash-lite
#   bash scripts/run-grading.sh --model together/openai/gpt-oss-120b --log-dir logs/nci-v31-gpt-oss-120b/
#   bash scripts/run-grading.sh --model google/gemini-2.5-flash-lite --dataset data/pilot_sample_12IC_tiered_seed42.csv
#
# Check status:
#   kill -0 $(cat logs/nci-v31-gpt-oss-120b/inspect.pid) && echo running || echo done
#
# After the run completes, append a row to logs/manifest.csv (Issue #41).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSPECT="$REPO_ROOT/.venv/bin/inspect"
ENV_FILE="$REPO_ROOT/.env"

MODEL=""
DATASET="data/nci_sample_v31_seed42.csv"
LOG_DIR=""
TEMPERATURE="0.0"

usage() {
    echo "Usage: $0 --model <model> [--dataset <path>] [--log-dir <dir>] [--temperature <float>]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)       MODEL="$2";       shift 2 ;;
        --dataset)     DATASET="$2";     shift 2 ;;
        --log-dir)     LOG_DIR="$2";     shift 2 ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        *) usage ;;
    esac
done

[[ -z "$MODEL" ]] && usage

# Auto-generate log dir from model name if not specified
if [[ -z "$LOG_DIR" ]]; then
    MODEL_SLUG="${MODEL//\//-}"
    LOG_DIR="$REPO_ROOT/logs/${MODEL_SLUG}/"
fi

mkdir -p "$LOG_DIR"

# Source environment variables
if [[ -f "$ENV_FILE" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
else
    echo "WARNING: $ENV_FILE not found — API keys must be set in environment"
fi

LOG_FILE="$LOG_DIR/inspect.log"
PID_FILE="$LOG_DIR/inspect.pid"

echo "Starting grading run:"
echo "  Model:    $MODEL"
echo "  Dataset:  $DATASET"
echo "  Log dir:  $LOG_DIR"
echo "  Log file: $LOG_FILE"

nohup "$INSPECT" eval "$REPO_ROOT/inspect_task.py" \
    --model "$MODEL" \
    -T "dataset_path=$DATASET" \
    --temperature "$TEMPERATURE" \
    --log-dir "$LOG_DIR" \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo "$PID" > "$PID_FILE"

echo "  PID:      $PID  (saved to $PID_FILE)"
echo ""
echo "Check status:  kill -0 \$(cat $PID_FILE) && echo running || echo done"
echo "Watch output:  tail -f $LOG_FILE"
echo ""
echo "REMINDER: When complete, append a row to logs/manifest.csv (Issue #41)"
