#!/bin/bash
# PreToolUse hook: block edits to data/RUBRIC.md
# RUBRIC.md is protected scientific content — definitions must not be modified
# without explicit direction from Manjari.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.file_path // ""')

if [[ "$FILE" == */data/RUBRIC.md ]]; then
  echo "RUBRIC.md is protected scientific content. Do not modify definitions without explicit direction." >&2
  exit 2
fi

exit 0
