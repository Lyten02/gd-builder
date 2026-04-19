"""Colored logging utilities using Rich"""

from datetime import datetime

from rich.console import Console
from rich.theme import Theme

# Custom theme for build output
custom_theme = Theme({
    "info": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red bold",
    "step": "cyan",
    "time": "cyan dim",
    "ts": "grey50",
})

console = Console(theme=custom_theme)


def _ts() -> str:
    """HH:MM:SS.mmm timestamp prefix — lets you see build-timing deltas to the ms."""
    now = datetime.now()
    return f"[ts]{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}[/ts]"


def log_info(message: str) -> None:
    """Log info message"""
    console.print(f"{_ts()} [info][INFO][/info] {message}")


def log_success(message: str) -> None:
    """Log success message"""
    console.print(f"{_ts()} [success][SUCCESS][/success] {message}")


def log_warn(message: str) -> None:
    """Log warning message"""
    console.print(f"{_ts()} [warning][WARN][/warning] {message}")


def log_error(message: str) -> None:
    """Log error message"""
    console.print(f"{_ts()} [error][ERROR][/error] {message}")


def log_step(message: str) -> None:
    """Log step message"""
    console.print(f"{_ts()} [step][STEP][/step] {message}")


def log_time(label: str, duration_ms: int) -> None:
    """Log timing info"""
    console.print(f"{_ts()} [time]  {label}: {duration_ms}ms[/time]")


def log_paths(project_dir: str, starter_dir: "str | None" = None) -> None:
    """Log project paths"""
    console.print(f"[info]Project Root:[/info] {project_dir}")
    if starter_dir:
        console.print(f"[info]Starter Lib:[/info]  {starter_dir}")
