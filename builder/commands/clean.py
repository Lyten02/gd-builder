"""Clean command implementation"""

import shutil
from pathlib import Path

from ..config import ProjectConfig
from ..utils.logger import log_step, log_success


def clean_command(config: ProjectConfig) -> bool:
    """Clean build artifacts"""

    log_step("Cleaning build artifacts...")

    dirs_to_remove = [
        config.bin_dir,
        config.project_dir / "dump",
        config.project_dir / "publish",
        config.project_dir / "logs",
    ]

    for dir_path in dirs_to_remove:
        if dir_path.exists():
            shutil.rmtree(dir_path)

    # Remove generated hxml files
    if config.build_dir.exists():
        for hxml in config.build_dir.glob("*_debug*.hxml"):
            hxml.unlink()
        for hxml in config.build_dir.glob("*_release*.hxml"):
            hxml.unlink()

    log_success("Clean complete")
    return True
