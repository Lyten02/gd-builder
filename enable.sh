#!/usr/bin/env bash
# enable.sh — bootstrap the build/ directory with default config.
#
# gd-builder is the build orchestrator itself; unlike feature modules, it does
# not register itself in sourcePaths (it ships no Haxe src/ for the game) and
# has no Claude skills to link. Its only job on enable is:
#
#   1. Clone `templates/profiles/main.json` → `build/profiles/main.json`
#      (project-owned — `cp -n` never overwrites existing).
#   2. Clone `templates/test.hxml` → `build/test.hxml` (same semantics).
#
# Re-running is safe: existing build/ files are preserved.
#
# Usage: bash modules/gd-builder/enable.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODULE_NAME="$(basename "$SCRIPT_DIR")"

log()  { printf '\033[36m[%s]\033[0m %s\n' "$MODULE_NAME" "$*"; }
ok()   { printf '\033[32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$*"; }

clone() {
  local src_rel="$1" dst_rel="$2"
  local src_abs="$SCRIPT_DIR/$src_rel"
  local dst_abs="$PROJECT_ROOT/$dst_rel"
  [[ -e "$src_abs" ]] || { warn "skip clone — template missing: $src_rel"; return; }
  mkdir -p "$(dirname "$dst_abs")"
  if [[ -e "$dst_abs" ]]; then
    log "clone skipped (exists): $dst_rel"
  else
    cp "$src_abs" "$dst_abs"
    ok "cloned $dst_rel (you can customize it)"
  fi
}

log "bootstrap build/ from gd-builder templates"
clone "templates/profiles/main.json" "build/profiles/main.json"
clone "templates/test.hxml"          "build/test.hxml"
log "done — run 'python modules/gd-builder/build.py build debug web' to verify"
