"""Subprocess management utilities"""

import subprocess
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .logger import log_error


@dataclass
class ProcessResult:
    """Result of running a subprocess"""
    success: bool
    stdout: str
    stderr: str
    duration_ms: int
    return_code: int


def run_command(
    cmd: list[str],
    cwd: Optional[Path] = None,
    capture_output: bool = True,
    timeout: Optional[int] = None,
    env: Optional[dict[str, str]] = None,
) -> ProcessResult:
    """Run a command and return result"""
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            env=env,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        return ProcessResult(
            success=result.returncode == 0,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            duration_ms=duration_ms,
            return_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        return ProcessResult(
            success=False,
            stdout="",
            stderr="Command timed out",
            duration_ms=duration_ms,
            return_code=-1,
        )
    except FileNotFoundError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return ProcessResult(
            success=False,
            stdout="",
            stderr=f"Command not found: {e}",
            duration_ms=duration_ms,
            return_code=-1,
        )


def run_haxe(args: list[str], cwd: Optional[Path] = None) -> ProcessResult:
    """Run haxe compiler with arguments"""
    return run_command(["haxe"] + args, cwd=cwd)


def run_node(script_path: Path, cwd: Optional[Path] = None) -> ProcessResult:
    """Run a JavaScript file with Node.js"""
    return run_command(["node", str(script_path)], cwd=cwd)


def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH"""
    result = run_command(["which", cmd])
    return result.success
