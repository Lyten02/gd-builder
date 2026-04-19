"""Parse utest stdout and render a tree-view grouped by project vs modules.

Usage (from build.py):

    from test_report import render
    print(render(stdout, project_root, exit_code, verbose=False))

Honors `NO_COLOR` env var and non-TTY stdout — both disable ANSI escapes
(emoji remain).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- data model ------------------------------------------------------------


@dataclass
class TestCase:
    name: str
    passed: bool
    detail: str = ""  # "" on pass, error message on fail


@dataclass
class Spec:
    fqn: str                          # e.g. "game.core.TestAABB"
    cases: list[TestCase] = field(default_factory=list)
    source: str = "<unknown>"         # "project" or "module:<name>" or "<unknown>"
    pkg: str = ""                     # derived from fqn

    @property
    def name(self) -> str:
        return self.fqn.rsplit(".", 1)[-1] if "." in self.fqn else self.fqn

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if not c.passed)

    @property
    def ok(self) -> bool:
        return self.failed == 0


@dataclass
class TestRunResult:
    specs: list[Spec] = field(default_factory=list)
    assertions: int = 0
    successes: int = 0
    errors: int = 0
    failures: int = 0
    warnings: int = 0
    execution_time: float = 0.0
    overall_ok: Optional[bool] = None  # from "results: ALL TESTS OK / SOME FAILURES"


# --- parsing ---------------------------------------------------------------


_RE_SPEC_FQN = re.compile(r"^([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)+)\s*$")
_RE_CASE_OK = re.compile(r"^\s{2,}(\w+):\s*OK\b")
# utest prints "FAILURE" / "ERROR" — not "FAIL" — so match the full tokens.
_RE_CASE_FAIL = re.compile(r"^\s{2,}(\w+):\s*(FAILURE|FAIL|ERROR|WARN\w*)\b(.*)$")
_RE_DETAIL = re.compile(r"^\s{4,}(.+)$")
_RE_KV = re.compile(r"^(assertations|successes|errors|failures|warnings):\s*(\d+)\s*$")
_RE_TIME = re.compile(r"^execution time:\s*([\d.]+)\s*$")
_RE_RESULTS = re.compile(r"^results:\s*(ALL TESTS OK|SOME TESTS FAILURES)")


def parse_utest_output(stdout: str) -> TestRunResult:
    """Parse the text report produced by utest's PrintReport."""
    result = TestRunResult()
    current_spec: Optional[Spec] = None
    last_fail: Optional[TestCase] = None  # for collecting multi-line failure details

    for raw in stdout.splitlines():
        line = raw.rstrip("\r")

        m = _RE_KV.match(line)
        if m:
            setattr(result, {
                "assertations": "assertions",
                "successes": "successes",
                "errors": "errors",
                "failures": "failures",
                "warnings": "warnings",
            }[m.group(1)], int(m.group(2)))
            last_fail = None
            continue

        m = _RE_TIME.match(line)
        if m:
            result.execution_time = float(m.group(1))
            last_fail = None
            continue

        m = _RE_RESULTS.match(line)
        if m:
            result.overall_ok = m.group(1) == "ALL TESTS OK"
            last_fail = None
            continue

        m = _RE_CASE_OK.match(line)
        if m and current_spec is not None:
            current_spec.cases.append(TestCase(name=m.group(1), passed=True))
            last_fail = None
            continue

        m = _RE_CASE_FAIL.match(line)
        if m and current_spec is not None:
            # The trailing fragment often contains only utest's progress
            # markers ("F.", "F", "E..") — drop those; keep only meaningful text.
            tail = m.group(3).strip()
            if re.fullmatch(r"[FE.\s]*", tail):
                tail = ""
            case = TestCase(name=m.group(1), passed=False, detail=tail)
            current_spec.cases.append(case)
            last_fail = case
            continue

        # Continuation lines (4+ spaces) belong to the most recent failure.
        m = _RE_DETAIL.match(line)
        if m and last_fail is not None:
            extra = m.group(1).strip()
            last_fail.detail = (last_fail.detail + " " + extra).strip() if last_fail.detail else extra
            continue

        m = _RE_SPEC_FQN.match(line)
        if m:
            # utest may emit its own trace lines starting with the file path;
            # require at least one dot AND no slash/colon to treat as spec fqn.
            fqn = m.group(1)
            if "/" in fqn or ":" in fqn:
                continue
            current_spec = Spec(fqn=fqn, pkg=fqn.rsplit(".", 1)[0] if "." in fqn else "")
            result.specs.append(current_spec)
            last_fail = None

    return result


# --- classification --------------------------------------------------------


def classify_sources(specs: list[Spec], project_root: Path) -> None:
    """Mutates each spec.source to 'project' | 'module:<name>' | '<unknown>'."""
    index: dict[str, list[Path]] = {}

    def _add(scan_root: Path) -> None:
        if not scan_root.exists():
            return
        for hx in scan_root.rglob("*.hx"):
            basename = hx.stem
            index.setdefault(basename, []).append(hx)

    _add(project_root / "test")
    modules_dir = project_root / "modules"
    if modules_dir.exists():
        for mod in modules_dir.iterdir():
            _add(mod / "test")

    for spec in specs:
        paths = index.get(spec.name)
        if not paths:
            spec.source = "<unknown>"
            continue
        # Prefer the first hit; classify by its location.
        path = paths[0]
        try:
            rel = path.relative_to(project_root).as_posix()
        except ValueError:
            spec.source = "<unknown>"
            continue
        if rel.startswith("test/"):
            spec.source = "project"
        elif rel.startswith("modules/"):
            parts = rel.split("/")
            if len(parts) >= 3 and parts[2] == "test":
                spec.source = f"module:{parts[1]}"
            else:
                spec.source = "<unknown>"
        else:
            spec.source = "<unknown>"


# --- rendering -------------------------------------------------------------


class _C:
    """ANSI color shortcuts; empty strings when colors disabled."""
    def __init__(self, enabled: bool):
        self.reset = "\033[0m" if enabled else ""
        self.bold = "\033[1m" if enabled else ""
        self.green = "\033[32m" if enabled else ""
        self.red = "\033[31m" if enabled else ""
        self.yellow = "\033[33m" if enabled else ""
        self.dim = "\033[90m" if enabled else ""
        self.cyan = "\033[36m" if enabled else ""


def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        # Still allow colors when invoked from another tool that captures stdout
        # but only if the user forced them via FORCE_COLOR.
        return bool(os.environ.get("FORCE_COLOR"))
    return True


def _source_label(src: str) -> tuple[str, str]:
    """Return (emoji, label) for a source bucket."""
    if src == "project":
        return ("🎮", "project")
    if src.startswith("module:"):
        return ("🧩", f"modules/{src.split(':', 1)[1]}")
    return ("❓", "<unknown>")


def _source_sort_key(src: str) -> tuple[int, str]:
    if src == "project":
        return (0, "")
    if src.startswith("module:"):
        return (1, src)
    return (2, src)


def render(
    stdout: str,
    project_root: Path,
    *,
    verbose: bool = False,
    scope: str = "",
) -> str:
    """Render utest stdout as a pretty tree report.

    `scope` is a short tag shown after the header, e.g. "module: loc-text"
    or "project only". Empty string means a full test run.
    """
    result = parse_utest_output(stdout)
    classify_sources(result.specs, project_root)

    c = _C(_colors_enabled())
    out: list[str] = []

    # Header
    scope_str = f"  {c.dim}· {scope}{c.reset}" if scope else ""
    out.append(f"{c.cyan}🧪 Running tests…{c.reset}{scope_str}")
    out.append("")

    if not result.specs:
        out.append(f"  {c.yellow}(no runnable specs){c.reset}")
        out.append("")
    else:
        # Group: source → package → [specs]
        by_source: dict[str, dict[str, list[Spec]]] = {}
        for spec in result.specs:
            by_source.setdefault(spec.source, {}).setdefault(spec.pkg or "<default>", []).append(spec)

        for src in sorted(by_source.keys(), key=_source_sort_key):
            emoji, label = _source_label(src)
            out.append(f"{emoji} {c.bold}{label}{c.reset}")

            by_pkg = by_source[src]
            # Compute alignment widths
            pkg_width = max(len(p) for p in by_pkg) + 2

            for pkg in sorted(by_pkg.keys()):
                specs = by_pkg[pkg]
                total_specs = len(specs)
                total_cases = sum(len(s.cases) for s in specs)
                total_failed = sum(s.failed for s in specs)

                spec_word = "spec " if total_specs == 1 else "specs"
                case_word = "test " if total_cases == 1 else "tests"
                status = (
                    f"{c.green}✅{c.reset}" if total_failed == 0
                    else f"{c.red}❌  ({total_failed} failed){c.reset}"
                )
                pkg_color = c.red if total_failed else c.reset
                out.append(
                    f"   📦 {pkg_color}{pkg.ljust(pkg_width)}{c.reset} "
                    f"{c.dim}{total_specs:>2} {spec_word} · {total_cases:>3} {case_word}{c.reset}  "
                    f"{status}"
                )

                if verbose or total_failed:
                    for spec in specs:
                        if not verbose and spec.ok:
                            continue
                        for case in spec.cases:
                            if not verbose and case.passed:
                                continue
                            mark = f"{c.green}✓{c.reset}" if case.passed else f"{c.red}✗{c.reset}"
                            name = f"{spec.name}.{case.name}"
                            if case.passed:
                                out.append(f"      {mark} {c.dim}{name}{c.reset}")
                            else:
                                out.append(f"      {mark} {c.red}{name}{c.reset}")
                                if case.detail:
                                    out.append(f"         {c.dim}{case.detail}{c.reset}")
            out.append("")

    # Footer. utest summary is authoritative; parsed spec/case counts are
    # only reliable when all tests pass (utest's text report lists every spec
    # then). On failure, utest emits only the failing specs — so we lean on
    # assertion counts, which are always present.
    all_ok = result.errors == 0 and result.failures == 0 and (
        result.overall_ok is not False
    )
    time_ms = int(round(result.execution_time * 1000))

    out.append(f"{c.dim}{'─' * 50}{c.reset}")

    if all_ok:
        total_specs = len(result.specs)
        total_cases = sum(len(s.cases) for s in result.specs)
        out.append(
            f"{c.bold}✨ {total_specs} specs · {total_cases} tests · "
            f"{result.assertions} assertions · ⚡ {time_ms}ms{c.reset}"
        )
        out.append(f"{c.green}{c.bold}🎯 all passing{c.reset}")
    else:
        failed = result.errors + result.failures
        out.append(
            f"{c.bold}✨ {result.successes}/{result.assertions} assertions passed"
            f" · ⚡ {time_ms}ms{c.reset}"
        )
        word = "failure" if failed == 1 else "failures"
        out.append(f"{c.red}{c.bold}💥 {failed} {word}{c.reset}")

    return "\n".join(out)


def is_success(stdout: str) -> bool:
    """Cheap check: parse totals and return True if 0 errors/failures."""
    result = parse_utest_output(stdout)
    return result.errors == 0 and result.failures == 0 and result.overall_ok is not False
