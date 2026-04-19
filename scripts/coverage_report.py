"""Parse c8 text-summary + utest output and render a pretty coverage dashboard.

Used by run_coverage.py. Honors `NO_COLOR` env var and non-TTY stdout.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# --- data model ------------------------------------------------------------


@dataclass
class Metric:
    name: str
    emoji: str
    percent: float
    passed: int
    total: int


# --- parsing ---------------------------------------------------------------


_RE_C8_LINE = re.compile(
    r"^\s*(Statements|Branches|Functions|Lines)\s*:\s*([\d.]+)%\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)"
)
_RE_UTEST_TIME = re.compile(r"^execution time:\s*([\d.]+)", re.MULTILINE)
_RE_UTEST_OK = re.compile(r"^\s{2,}\w+:\s*OK\b", re.MULTILINE)
_RE_UTEST_FAIL = re.compile(r"^\s{2,}\w+:\s*(FAILURE|FAIL|ERROR)\b", re.MULTILINE)
_RE_UTEST_RESULT = re.compile(r"^results:\s*(ALL TESTS OK|SOME TESTS FAILURES)", re.MULTILINE)


# Emoji prefix is pre-padded to the same visual width (2 cells) so the
# table lines up. ⚙️ (U+2699 + VS16) is visually 2 cells in most modern
# terminals; the rest (📝 📏 🌿) are 2 cells by default.
_METRIC_META = {
    "Statements": ("📝", "Statements"),
    "Lines":      ("📏", "Lines"),
    "Functions":  ("⚙️", "Functions"),
    "Branches":   ("🌿", "Branches"),
}
_METRIC_ORDER = ["Statements", "Lines", "Functions", "Branches"]


def parse_c8(stdout: str) -> list[Metric]:
    metrics: list[Metric] = []
    for line in stdout.splitlines():
        m = _RE_C8_LINE.match(line)
        if not m:
            continue
        name = m.group(1)
        emoji, display = _METRIC_META.get(name, ("", name))
        metrics.append(Metric(
            name=display,
            emoji=emoji,
            percent=float(m.group(2)),
            passed=int(m.group(3)),
            total=int(m.group(4)),
        ))
    metrics.sort(key=lambda x: _METRIC_ORDER.index(x.name) if x.name in _METRIC_ORDER else 99)
    return metrics


def parse_tests(stdout: str) -> tuple[int, int, float, Optional[bool]]:
    """Return (total_tests, failed_tests, execution_time, all_ok)."""
    ok = len(_RE_UTEST_OK.findall(stdout))
    fails = len(_RE_UTEST_FAIL.findall(stdout))
    total = ok + fails
    time_m = _RE_UTEST_TIME.search(stdout)
    time = float(time_m.group(1)) if time_m else 0.0
    res_m = _RE_UTEST_RESULT.search(stdout)
    all_ok = res_m.group(1) == "ALL TESTS OK" if res_m else None
    return total, fails, time, all_ok


# --- rendering -------------------------------------------------------------


class _C:
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
        return bool(os.environ.get("FORCE_COLOR"))
    return True


def _bar(pct: float, width: int = 20) -> str:
    filled = int(round(pct / 100 * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _status(pct: float, c: _C) -> tuple[str, str]:
    """Return (emoji, color_code) based on threshold: ≥90 green, ≥70 yellow, <70 red."""
    if pct >= 90:
        return "🟢", c.green
    if pct >= 70:
        return "🟡", c.yellow
    return "🔴", c.red


def render(
    stdout: str,
    report_path: Path,
    *,
    scope: str = "all",
    project_root: Optional[Path] = None,
) -> str:
    """Render coverage dashboard from combined c8+utest stdout."""
    metrics = parse_c8(stdout)
    test_total, test_failed, exec_time, all_ok = parse_tests(stdout)
    c = _C(_colors_enabled())

    out: list[str] = []
    time_ms = int(round(exec_time * 1000))
    time_str = f"{time_ms}ms" if time_ms < 1000 else f"{time_ms / 1000:.1f}s"

    # Header
    if all_ok is False or test_failed > 0:
        tests_badge = f"{c.red}❌ {test_failed} failed / {test_total} tests{c.reset}"
    elif test_total > 0:
        tests_badge = f"{c.green}✅ {test_total} tests{c.reset}"
    else:
        tests_badge = f"{c.yellow}⚠ no tests{c.reset}"

    out.append(
        f"{c.cyan}📊 Test coverage{c.reset}  {c.dim}·{c.reset}  "
        f"scope: {scope}  {c.dim}·{c.reset}  ⚡ {time_str}  {c.dim}·{c.reset}  {tests_badge}"
    )
    out.append("")

    if not metrics:
        out.append(f"   {c.yellow}(c8 summary not found — coverage disabled or failed){c.reset}")
        out.append("")
        return "\n".join(out)

    # Table
    max_total = max(m.total for m in metrics)
    total_width = len(f"{max_total:,}".replace(",", ""))  # digit count

    header = (
        f"   {c.dim}Metric          %        Progress               "
        f"{'Passed'.rjust(total_width)} / {'Total'.rjust(total_width)}{c.reset}"
    )
    out.append(header)
    out.append(f"   {c.dim}" + "─" * 60 + f"{c.reset}")

    for m in metrics:
        status_emoji, status_color = _status(m.percent, c)
        # Pad the NAME portion to a fixed char-width so columns align even
        # when emoji cell-widths differ slightly between terminals.
        name_cell = f"{m.emoji} {m.name.ljust(10)}"
        pct_cell = f"{m.percent:5.2f}%".rjust(7)
        bar_str = _bar(m.percent, 20)
        bar_cell = f"{status_color}{bar_str}{c.reset}"
        passed_cell = f"{m.passed}".rjust(total_width)
        total_cell = f"{m.total}".rjust(total_width)
        out.append(
            f"   {name_cell}  {status_color}{pct_cell}{c.reset}   "
            f"{bar_cell}   {passed_cell} / {total_cell}   {status_emoji}"
        )

    out.append("")

    # Footer: report link
    if project_root:
        try:
            rel = report_path.relative_to(project_root).as_posix()
        except ValueError:
            rel = str(report_path)
    else:
        rel = str(report_path)
    out.append(f"   🔗 {c.cyan}{rel}{c.reset}")

    return "\n".join(out)
