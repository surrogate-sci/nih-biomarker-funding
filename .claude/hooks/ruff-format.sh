#!/bin/bash
# PostToolUse hook: auto-format Python files after Edit
# Runs ruff format + ruff check --fix; non-fatal on errors.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

if [[ "$FILE" == *.py ]]; then
  ruff format "$FILE" 2>/dev/null || true
  ruff check --fix "$FILE" 2>/dev/null || true
fi

exit 0
