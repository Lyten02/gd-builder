"""Path helper utilities."""

from pathlib import Path


def path_for_project(path: Path, project_dir: Path) -> str:
    """Return a project-relative path when possible, otherwise absolute."""
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)
