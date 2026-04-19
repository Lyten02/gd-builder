"""Standalone lint: applies project rules A–I per module, plus god-file check.

Usage:
    python scripts/lint.py                  # project + all modules
    python scripts/lint.py --module=<name>  # single module only
    python scripts/lint.py --project-only   # skip modules

Replaces the dormant monkey-patch that hooked into gd-builder's `lint` command
(absent in current gd-builder). Reuses RULES and run_project_rules from
scripts/lint_rules.py.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# lint.py ships inside gd-builder; invoked from build.py which lives in the
# same module. Resolving __file__ would scan gd-builder's own sources — use
# CWD so the project itself is scanned.
ROOT = Path.cwd()
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from lint_rules import run_project_rules  # type: ignore

GOD_FILE_LIMIT = 200

# Vendored modules (git subtrees we don't own) — skipped by default. Lint
# explicitly with `--module=<name>` if you need to audit them.
VENDORED_MODULES = {"haxeheaps-starter", "gd-builder"}


@dataclass
class _MiniConfig:
    project_dir: Path


def _roots_for(module: str | None, project_only: bool) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if module:
        p = ROOT / "modules" / module
        if not p.exists():
            print(f"[ERROR] module not found: {p}", file=sys.stderr)
            sys.exit(2)
        roots.append((module, p))
        return roots
    roots.append(("<project>", ROOT))
    if project_only:
        return roots
    mods = ROOT / "modules"
    if mods.exists():
        for sub in sorted(mods.iterdir()):
            if not sub.is_dir() or not (sub / "src").exists():
                continue
            if sub.name in VENDORED_MODULES:
                continue
            roots.append((sub.name, sub))
    return roots


def _god_file_check(label: str, root: Path) -> bool:
    offenders: list[tuple[str, int]] = []
    for base in (root / "src", root / "test"):
        if not base.exists():
            continue
        for p in base.rglob("*.hx"):
            try:
                n = sum(1 for _ in p.open("r", encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if n > GOD_FILE_LIMIT:
                offenders.append((p.relative_to(root).as_posix(), n))
    if not offenders:
        return True
    print(f"[ERROR] [{label}] god-file(s) exceeding {GOD_FILE_LIMIT} LOC:")
    for rel, n in offenders:
        print(f"  {rel}: {n} lines")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default=None)
    ap.add_argument("--project-only", action="store_true")
    args = ap.parse_args()

    all_ok = True
    for label, root in _roots_for(args.module, args.project_only):
        print(f"\n=== [{label}] {root} ===")
        rc = run_project_rules(_MiniConfig(project_dir=root))
        gok = _god_file_check(label, root)
        all_ok = all_ok and bool(rc) and gok
    print()
    if all_ok:
        print("[SUCCESS] lint clean across all roots")
        return 0
    print("[ERROR] lint violations present")
    return 1


if __name__ == "__main__":
    sys.exit(main())
