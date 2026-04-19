#!/usr/bin/env bash
# delete.sh — DISABLE this module (remove symlinks) and PERMANENTLY delete its directory.
# Usage: bash modules/localization-base/delete.sh
#
# DESTRUCTIVE: removes modules/localization-base/ entirely. No undo from this script.
# If the module has uncommitted/unpushed changes, they are lost.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_NAME="$(basename "$SCRIPT_DIR")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "About to PERMANENTLY delete: $SCRIPT_DIR"
echo "This also removes any symlinks in $PROJECT_ROOT/.claude/skills/ that point here."
read -r -p "Type the module name ('$MODULE_NAME') to confirm: " confirm
if [[ "$confirm" != "$MODULE_NAME" ]]; then
  echo "confirmation failed — aborted"
  exit 1
fi

# 1. Remove symlinks (disable)
if [[ -f "$SCRIPT_DIR/disable.sh" ]]; then
  bash "$SCRIPT_DIR/disable.sh" || echo "warn: disable.sh failed — continuing"
else
  echo "no disable.sh — skipping unlink step"
fi

# 2. Move out of the dir we are about to delete
cd "$PROJECT_ROOT"

# 3. Remove the module directory
rm -rf "$SCRIPT_DIR"
echo "removed $SCRIPT_DIR"
