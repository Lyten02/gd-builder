"""Compile tests + run c8 V8-coverage on the resulting JS bundle.

Haxe emits bin/test/test.js + test.js.map; c8 reads the map so the HTML
report can drill down to original `.hx` source (requires `-D js-source-map`
and `-D source-map-content` in build/test.hxml).

Flags:
    --module=<name>   Scope to modules/<name>/test via -D module_test=<name>.
    --project-only    Skip module tests (-D project_only_test=1).
    --ai              Emit JSON summary parsed from c8 text-summary.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on emoji.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

# run_coverage.py ships in gd-builder; invoked from build.py which lives in
# the same module. Resolving __file__ would scan the module — use CWD so the
# host project's build/ and logs/ are what gets touched.
ROOT = Path.cwd()
MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_DIR))

TEST_HXML = ROOT / "build" / "test.hxml"
TEST_JS = ROOT / "bin" / "test" / "test.js"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--module", default=None,
                   help="Cover only tests of modules/<name>/test.")
    p.add_argument("--project-only", action="store_true",
                   help="Skip module tests; cover only project test/.")
    p.add_argument("--ai", action="store_true",
                   help="Emit JSON summary on stdout.")
    return p.parse_args()


def _scope_label(args: argparse.Namespace) -> str:
    if args.module:
        return f"module: {args.module}"
    if args.project_only:
        return "project only"
    return "all"


def main() -> int:
    args = _parse_args()

    haxe = shutil.which("haxe")
    if haxe is None:
        print("[coverage] haxe not on PATH", file=sys.stderr)
        return 127

    if not TEST_HXML.exists():
        print(f"[coverage] test.hxml missing at {TEST_HXML}", file=sys.stderr)
        return 2

    haxe_cmd = [haxe, str(TEST_HXML)]
    if args.module:
        haxe_cmd += ["-D", f"module_test={args.module}"]
    if args.project_only:
        haxe_cmd += ["-D", "project_only_test=1"]

    # Compile tests (silent — haxe warnings flow to stderr, stdout captured).
    compile_proc = subprocess.run(
        haxe_cmd, cwd=str(ROOT), capture_output=True, text=True
    )
    if compile_proc.returncode != 0:
        sys.stderr.write(compile_proc.stderr or compile_proc.stdout or "")
        print(f"[coverage] haxe compile failed (rc={compile_proc.returncode})",
              file=sys.stderr)
        return compile_proc.returncode

    if not TEST_JS.exists():
        print(f"[coverage] {TEST_JS} missing after compile", file=sys.stderr)
        return 1

    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx is None:
        print("[coverage] npx not on PATH — install Node.js first", file=sys.stderr)
        return 127

    reports_dir = ROOT / "logs" / "coverage"
    if args.module:
        reports_dir = reports_dir / args.module
    elif args.project_only:
        reports_dir = reports_dir / "_project_only"

    c8_cmd = [
        npx, "--yes", "c8",
        "--reporter=text-summary",
        "--reporter=html",
        f"--reports-dir={reports_dir}",
        "--include=bin/test/test.js",
        "--exclude-after-remap=false",
        "node", str(TEST_JS),
    ]

    # Run c8 silently — its stdout contains the utest report + c8 text-summary.
    proc = subprocess.run(c8_cmd, cwd=str(ROOT), capture_output=True, text=True)
    combined_stdout = proc.stdout or ""

    if args.ai:
        import coverage_report  # type: ignore
        metrics = coverage_report.parse_c8(combined_stdout)
        summary = {m.name.lower(): m.percent for m in metrics}
        print(json.dumps({
            "ok": proc.returncode == 0,
            "module": args.module,
            "project_only": args.project_only,
            "report_html": str(reports_dir / "index.html"),
            **summary,
        }, ensure_ascii=False))
        return proc.returncode

    # Pretty dashboard.
    import coverage_report  # type: ignore
    scope = _scope_label(args)
    report_path = reports_dir / "index.html"

    # If tests failed, show the focused failure block first, then coverage.
    _, failed, _, all_ok = coverage_report.parse_tests(combined_stdout)
    if failed > 0 or all_ok is False:
        try:
            import test_report  # type: ignore
            sys.path.insert(0, str(MODULE_DIR))
            print(test_report.render(combined_stdout, ROOT, verbose=False, scope=scope))
            print()
        except Exception:
            # Fall back to raw stderr-ish dump on parsing issues.
            sys.stderr.write(proc.stderr or "")

    print(coverage_report.render(
        combined_stdout, report_path, scope=scope, project_root=ROOT
    ))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
