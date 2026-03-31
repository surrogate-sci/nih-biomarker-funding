#!/usr/bin/env bash
# Download obra/superpowers skills into .claude/skills/ for environments
# without access to user-level skills (e.g., mobile Claude Code sessions).
# Idempotent — skips download if skills already present.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/.claude/skills"
SENTINEL="$SKILLS_DIR/using-superpowers/SKILL.md"

if [ -f "$SENTINEL" ]; then
    echo "Superpowers skills already present, skipping download."
    exit 0
fi

echo "Downloading obra/superpowers skills..."
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

git clone --depth 1 https://github.com/obra/superpowers.git "$TMPDIR/superpowers" 2>&1

mkdir -p "$SKILLS_DIR"
cp -r "$TMPDIR/superpowers/skills/"* "$SKILLS_DIR/"

echo "Installed $(ls -d "$SKILLS_DIR"/*/  | wc -l) skills into .claude/skills/"
