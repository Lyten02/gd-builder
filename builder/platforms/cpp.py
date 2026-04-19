"""C++ platform implementation (native binary via HashLink)"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .base import BasePlatform
from ..config import ProjectConfig
from ..utils.logger import log_step, log_success, log_error
from ..utils.process import run_command


class CppPlatform(BasePlatform):
    """C++ platform (native binary via HashLink C output)"""

    @property
    def name(self) -> str:
        return "cpp"

    @property
    def output_dir(self) -> Path:
        return self.config.bin_dir / "hlc"

    @property
    def binary_path(self) -> Path:
        return self.config.bin_dir / "game"

    def prepare(self) -> bool:
        """Create output directory"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return True

    def post_build(self) -> bool:
        """Compile C code to native binary"""
        log_step("Compiling C to native binary...")

        # Find Makefile
        makefile_path = self._find_makefile()
        if not makefile_path:
            log_error("Makefile.hlc not found")
            return False

        # Run make
        result = run_command(
            [
                "make",
                "-f", str(makefile_path),
                f"PROJECT_DIR={self.config.project_dir}",
                f"BIN_DIR={self.config.bin_dir}",
                f"RES_DIR={self.config.res_dir}",
            ],
            cwd=self.config.project_dir,
        )

        if result.success:
            log_success(f"Native binary created: {self.binary_path}")
            return True
        else:
            log_error(f"C compilation failed: {result.stderr}")
            print("\a", end="", flush=True)  # Bell
            return False

    def run(self) -> bool:
        """Run the native binary"""
        if not self.binary_path.exists():
            log_error(f"Binary not found: {self.binary_path}")
            return False

        log_success(f"Running {self.binary_path}")
        subprocess.Popen([str(self.binary_path)], cwd=self.config.project_dir)
        return True

    def get_run_command(self) -> list[str]:
        return [str(self.binary_path)]

    def _find_makefile(self) -> Path | None:
        """Find Makefile.hlc"""
        # Check build directory first (preferred location after restructure)
        makefile = self.config.build_dir / "Makefile.hlc"
        if makefile.exists():
            return makefile

        # Fallback: check starter tools (legacy)
        if self.config.starter_dir:
            makefile = self.config.starter_dir / "tools" / "Makefile.hlc"
            if makefile.exists():
                return makefile

        return None
