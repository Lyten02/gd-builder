#!/usr/bin/env python3
"""Project build entry point — owns build / run / watch / publish / clean /
test / lint for the modular Haxe/Heaps ecosystem.

Invoked via full module path from the project root:

    python modules/gd-builder/build.py build debug web
    python modules/gd-builder/build.py test [--module=<name>] [--project-only] [--ai]
    python modules/gd-builder/build.py lint [--module=<name>] [--project-only]
    python modules/gd-builder/build.py watch debug web
    python modules/gd-builder/build.py publish release web
    python modules/gd-builder/build.py clean

All module lookups resolve relative to CWD (the project root). gd-builder's own
source lives next to this file and is imported first.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Windows consoles default to cp1252 and choke on emoji. Reconfigure both
# stdout and stderr to UTF-8 with replacement fallback.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

# build.py lives inside the gd-builder module; invoke via full module path.
ROOT = Path.cwd()
MODULE_DIR = Path(__file__).resolve().parent
BUILDER_SCRIPTS = MODULE_DIR / "scripts"
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(BUILDER_SCRIPTS))

from builder.config import ProjectConfig  # type: ignore

# --- gd-builder patches ---------------------------------------------------
#
# These adjustments are driven by the modular architecture of the host
# project, not by gd-builder's core. They run at import time so every
# command observes the patched behavior.

# 1. check_command_exists uses `which`, absent on vanilla Windows shells.
import shutil as _shutil
from builder.utils import process as _proc_mod  # type: ignore
_proc_mod.check_command_exists = lambda cmd: _shutil.which(cmd) is not None  # type: ignore[assignment]

# 2. build_dir lives under build/ at the project root. Generated hxml files
#    colocate with profiles/main.json (the project-owned config cloned by
#    gd-builder/enable.sh from templates/profiles/main.json).
_ORIG_FROM_PROJECT_ROOT = ProjectConfig.from_project_root.__func__


@classmethod
def _from_project_root_with_build_dir(cls, project_dir: Optional[Path] = None):
    config = _ORIG_FROM_PROJECT_ROOT(cls, project_dir)
    config.build_dir = config.project_dir / "build"
    config.build_dir.mkdir(parents=True, exist_ok=True)
    (config.build_dir / "profiles").mkdir(parents=True, exist_ok=True)
    return config


ProjectConfig.from_project_root = _from_project_root_with_build_dir  # type: ignore[method-assign]

# 3. Post-process generated hxml: apply libs from modules/build/profiles/main.json
#    (gd-builder hardcodes `-lib heaps`) and append module-contributed macros.
from builder.services.haxe import HaxeCompiler as _HaxeCompiler  # type: ignore
_ORIG_GENERATE_HXML = _HaxeCompiler.generate_hxml
_I18N_MACRO_LINE = "--macro loc.text.macro.I18nValidator.scan()"


def _load_profile_libs() -> list[str]:
    import json
    profile = ROOT / "build" / "profiles" / "main.json"
    if not profile.exists():
        return []
    try:
        return list(json.loads(profile.read_text()).get("libs", []))
    except (ValueError, OSError):
        return []


def _generate_hxml_with_project_fixes(self, platform, mode):
    path = _ORIG_GENERATE_HXML(self, platform, mode)
    text = path.read_text()
    lines = text.splitlines()

    libs_from_profile = _load_profile_libs()
    if libs_from_profile:
        existing = {ln.strip() for ln in lines if ln.strip().startswith("-lib ")}
        heaps_variant = next((l for l in libs_from_profile if l.split(":", 1)[0] == "heaps"), None)
        if heaps_variant and heaps_variant != "heaps":
            for i, ln in enumerate(lines):
                if ln.strip() == "-lib heaps":
                    lines[i] = f"-lib {heaps_variant}"
                    existing.discard("-lib heaps")
                    existing.add(f"-lib {heaps_variant}")
        for lib in libs_from_profile:
            ln = f"-lib {lib}"
            if ln not in existing:
                lines.append(ln)
                existing.add(ln)

    if _I18N_MACRO_LINE not in text:
        lines.append(_I18N_MACRO_LINE)

    path.write_text("\n".join(lines) + "\n")
    return path


_HaxeCompiler.generate_hxml = _generate_hxml_with_project_fixes  # type: ignore[method-assign]

# --- Extra commands -------------------------------------------------------

from builder import cli as _cli_mod  # type: ignore
import click as _click  # type: ignore


@_cli_mod.cli.command("lint")
@_click.option("--module", "module_name", default=None,
               help="Lint a single module instead of project + all modules.")
@_click.option("--project-only", is_flag=True,
               help="Skip modules; lint only the project root.")
@_click.pass_context
def _lint_cmd(ctx, module_name, project_only):
    """Run project anti-hallucination rules (A–H) + god-file check."""
    import subprocess
    argv = [sys.executable, str(BUILDER_SCRIPTS / "lint.py")]
    if module_name:
        argv += [f"--module={module_name}"]
    if project_only:
        argv += ["--project-only"]
    rc = subprocess.run(argv, cwd=str(ROOT)).returncode
    ctx.exit(rc)


@_cli_mod.cli.command("coverage")
@_click.option("--module", "module_name", default=None,
               help="Cover tests of a single module.")
@_click.option("--project-only", is_flag=True,
               help="Skip modules; cover only project test/.")
@_click.option("--ai", "ai_output", is_flag=True,
               help="Emit machine-readable JSON summary on stdout.")
@_click.pass_context
def _coverage_cmd(ctx, module_name, project_only, ai_output):
    """Run tests under c8 V8-coverage (requires Node.js + npx on PATH).

    HTML report lands in logs/coverage/ (or logs/coverage/<scope>/ when
    --module or --project-only is used).
    """
    import subprocess
    argv = [sys.executable, str(BUILDER_SCRIPTS / "run_coverage.py")]
    if module_name:
        argv += [f"--module={module_name}"]
    if project_only:
        argv += ["--project-only"]
    if ai_output:
        argv += ["--ai"]
    rc = subprocess.run(argv, cwd=str(ROOT)).returncode
    ctx.exit(rc)


# Replace gd-builder's `test` command with an extended version that accepts
# --module=<name> / --project-only / --ai. These propagate to the TestCollector
# macro (-D flags) and optionally emit a JSON summary for AI/CI consumption.
if "test" in _cli_mod.cli.commands:
    del _cli_mod.cli.commands["test"]


@_cli_mod.cli.command("test")
@_click.option("--module", "module_name", default=None,
               help="Run tests for a single module (scans modules/<name>/test).")
@_click.option("--project-only", is_flag=True,
               help="Skip module tests; run only project's test/ dir.")
@_click.option("--ai", "ai_output", is_flag=True,
               help="Emit machine-readable JSON summary on stdout.")
@_click.option("--verbose", "-v", is_flag=True)
@_click.pass_context
def _test_cmd(ctx, module_name, project_only, ai_output, verbose):
    """Run Haxe tests (utest) under Node.js."""
    import json
    import subprocess
    config = ProjectConfig.from_project_root(Path(ctx.obj.get("project_dir")) if ctx.obj.get("project_dir") else None)
    test_hxml = config.build_dir / "test.hxml"
    if not test_hxml.exists():
        sys.stderr.write(f"[ERROR] test.hxml not found at {test_hxml}\n")
        ctx.exit(2)

    haxe_cmd = ["haxe", str(test_hxml)]
    if module_name:
        haxe_cmd += ["-D", f"module_test={module_name}"]
    if project_only:
        haxe_cmd += ["-D", "project_only_test=1"]

    compile_proc = subprocess.run(haxe_cmd, cwd=str(config.project_dir),
                                   capture_output=True, text=True)
    if compile_proc.returncode != 0:
        if ai_output:
            print(json.dumps({"ok": False, "stage": "compile",
                              "stderr": compile_proc.stderr}))
        else:
            sys.stderr.write(compile_proc.stderr)
        ctx.exit(1)

    test_js = config.bin_dir / "test" / "test.js"
    if not test_js.exists():
        sys.stderr.write(f"[ERROR] Test output not found: {test_js}\n")
        ctx.exit(2)

    run_proc = subprocess.run(["node", str(test_js)], cwd=str(config.project_dir),
                               capture_output=True, text=True)
    stdout = run_proc.stdout or ""
    stderr = run_proc.stderr or ""
    if ai_output:
        asserts = _int_match(r"assertations:\s*(\d+)", stdout)
        successes = _int_match(r"successes:\s*(\d+)", stdout)
        errors = _int_match(r"errors:\s*(\d+)", stdout)
        failures = _int_match(r"failures:\s*(\d+)", stdout)
        summary = {
            "ok": run_proc.returncode == 0 and errors == 0 and failures == 0,
            "module": module_name,
            "project_only": project_only,
            "assertions": asserts,
            "successes": successes,
            "errors": errors,
            "failures": failures,
            "failing_lines": _extract_failures(stdout),
        }
        print(json.dumps(summary, ensure_ascii=False))
    else:
        import test_report  # type: ignore
        scope = ""
        if module_name:
            scope = f"module: {module_name}"
        elif project_only:
            scope = "project only"
        print(test_report.render(stdout, config.project_dir, verbose=verbose, scope=scope))
        if stderr:
            sys.stderr.write(stderr)
    ctx.exit(0 if run_proc.returncode == 0 else 1)


def _int_match(pattern: str, text: str) -> int:
    import re
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def _extract_failures(text: str) -> list:
    import re
    return [line.strip() for line in text.splitlines()
            if re.search(r"\b(FAIL|ERROR)\b", line)]


from builder.cli import main  # type: ignore


if __name__ == "__main__":
    main()
