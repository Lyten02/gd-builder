"""Project-specific lint rules for Test1234 (Haxe/Heaps + ECS + MVP).

Catches common LLM hallucinations: Unity idioms, React/Browser APIs, h3d in a
2D game, View↔World coupling, Domkit templates missing SRC, direct hxd.Key
usage, Heaps deps leaking into tests, etc.

Plain stdlib. Invoked from build.py after starter's lint_command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# ---------- Rule model ----------

@dataclass
class Rule:
    id: str
    msg: str
    pattern: Optional[str] = None                  # regex; matched per non-comment line
    glob: str = "src/**/*.hx"                      # file scope
    exclude_globs: tuple[str, ...] = field(default_factory=tuple)
    predicate: Optional[Callable[[str], bool]] = None  # whole-file check (True = violation)


def _uiComp_missing_SRC(text: str) -> bool:
    return ("@:uiComp" in text) and ("static var SRC" not in text)


RULES: list[Rule] = [
    Rule(
        id="A",
        # h3d.Engine is legit bootstrap config (antialiasing etc.) — forbid only scene/prim/mat/anim.
        pattern=r"\bh3d\.(scene|prim|mat|anim|shader|pass)\b",
        glob="src/**/*.hx",
        msg="h3d scene-graph forbidden — project is 2D (use h2d).",
    ),
    Rule(
        id="B",
        pattern=r"^\s*import\s+(unity|three|browser|js\.html|react|vue)\b",
        glob="**/*.hx",
        msg="Foreign-ecosystem import (Unity / React / Browser / Three) — not available in Haxe/Heaps.",
    ),
    Rule(
        id="C",
        pattern=r"\bMonoBehaviour\b|\[SerializeField\]|@:serialize\b",
        glob="**/*.hx",
        msg="Unity/C# idiom — ECS components use `implements Component`, no MonoBehaviour / SerializeField.",
    ),
    Rule(
        id="D",
        pattern=r"^\s*import\s+h(2d|xd|3d)\b",
        glob="test/**/*.hx",
        msg="Tests must be pure logic — no h2d/hxd/h3d imports.",
    ),
    Rule(
        id="E",
        pattern=r"\bWorld\b",
        glob="src/game/ui/**/*View.hx",
        msg="View must not reference World — MVP: Presenter reads World, View only renders its Model.",
    ),
    Rule(
        id="F",
        pattern=r"^\s*import\s+h(2d|xd)\b",
        glob="src/game/ui/**/*Presenter.hx",
        msg="Presenter must not import h2d/hxd — Presenters don't draw.",
    ),
    Rule(
        id="G",
        predicate=_uiComp_missing_SRC,
        glob="src/game/ui/**/*.hx",
        msg="@:uiComp class missing `static var SRC` Domkit template.",
    ),
    Rule(
        id="H",
        pattern=r"\bhxd\.Key\.",
        glob="src/game/**/*.hx",
        exclude_globs=("src/game/input/**",),
        msg="hxd.Key.* forbidden in game code — use GameAction + InputBindings.",
    ),
    # Rule I: user-facing strings must go through I18n.t / GameI18n.
    # Matches multi-word capitalized literals ("Take plate", "Game Over!"); a
    # dotted i18n key like "messages.caught" has no space so is not caught. A
    # heuristic — whitelist below handles known-safe literals (trace, paths).
    Rule(
        id="I",
        pattern=r'"[A-Z][A-Za-z]+ [A-Za-z!\'\.\-][A-Za-z !\'\.\-]*"',
        glob="src/game/**/*.hx",
        exclude_globs=(
            "src/game/input/**",
            "src/game/map/**",
            "src/game/core/**",
            "src/game/ui/debug/**",
            "src/game/i18n/**",
        ),
        msg="Hardcoded user-facing string — use I18n.t('ns.key') / GameI18n.*.",
    ),
]


# ---------- Scanner ----------

def _is_comment_line(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("//") or s.startswith("*")


def _iter_files(root: Path, glob: str, exclude_globs: tuple[str, ...]):
    for p in root.glob(glob):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(_matches(rel, ex) for ex in exclude_globs):
            continue
        yield p


def _matches(rel_posix: str, glob: str) -> bool:
    # Convert glob to simple regex: ** → .*, * → [^/]*, escape rest.
    import fnmatch
    # fnmatch handles * but not **; do ** manually.
    pat = glob.replace("**/", "__DSTAR__/").replace("**", "__DSTAR__")
    regex = fnmatch.translate(pat).replace("__DSTAR__", ".*")
    return re.match(regex, rel_posix) is not None


def _scan_rule(root: Path, rule: Rule) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for p in _iter_files(root, rule.glob, rule.exclude_globs):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = p.relative_to(root).as_posix()

        if rule.predicate is not None:
            if rule.predicate(text):
                hits.append((rel, 1, "<file-level check>"))
            continue

        if rule.pattern is None:
            continue
        rx = re.compile(rule.pattern)
        for i, line in enumerate(text.splitlines(), start=1):
            if _is_comment_line(line):
                continue
            m = rx.search(line)
            if m:
                hits.append((rel, i, m.group(0)))
    return hits


# ---------- Entry point ----------

def run_project_rules(config) -> bool:
    root = Path(config.project_dir)
    print("[STEP] [project-rules] scanning for anti-hallucination patterns")
    all_ok = True
    total_hits = 0
    for rule in RULES:
        hits = _scan_rule(root, rule)
        if not hits:
            continue
        all_ok = False
        total_hits += len(hits)
        print(f"[ERROR] [project-rules] {rule.id}: {rule.msg}")
        for rel, line, token in hits:
            print(f"  {rel}:{line}  {token!r}")
    if all_ok:
        print(f"[SUCCESS] [project-rules] OK — {len(RULES)} rules clean")
    else:
        print(f"[ERROR] [project-rules] {total_hits} violation(s) across {len(RULES)} rules")
    return all_ok
