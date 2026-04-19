#!/usr/bin/env bash
# disable.sh — no-op for the build orchestrator.
#
# gd-builder is the build system itself — it owns `build.py`, the hxml
# generator, and the lint/test commands. Nothing to deactivate: disabling it
# would leave the project without a builder. If you really want to remove
# gd-builder from the project, use `delete.sh`.
#
# Cloned files in `build/` (profiles/main.json, test.hxml) are project-owned
# and not touched here — consistent with other modules' disable semantics.
#
# Usage: bash modules/gd-builder/disable.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_NAME="$(basename "$SCRIPT_DIR")"

printf '\033[36m[%s]\033[0m %s\n' "$MODULE_NAME" \
  "gd-builder is the build orchestrator — nothing to disable."
printf '  * Cloned build/ files stay (project owns them).\n'
printf '  * To fully remove, run: bash modules/%s/delete.sh\n' "$MODULE_NAME"
