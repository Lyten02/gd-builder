"""Vite integration for React development"""

import subprocess
import time
from pathlib import Path
from typing import Optional

from ..config import ProjectConfig
from ..utils.logger import log_step, log_success, log_error, log_info
from ..utils.process import run_command


class ViteServer:
    """Vite development server wrapper"""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None

    @property
    def ui_dir(self) -> Path:
        return self.config.ui_dir

    def install_dependencies(self) -> bool:
        """Install npm dependencies if needed"""
        if not self.ui_dir.exists():
            log_error(f"UI directory not found: {self.ui_dir}")
            return False

        if self._missing_dependencies():
            log_step("Installing React dependencies...")
            result = run_command(["npm", "install"], cwd=self.ui_dir)
            if not result.success:
                log_error(f"npm install failed: {result.stderr}")
                return False

        return True

    def _missing_dependencies(self) -> bool:
        required = (
            self.ui_dir / "node_modules" / "vite" / "package.json",
            self.ui_dir / "node_modules" / "react" / "package.json",
            self.ui_dir / "node_modules" / "react-dom" / "package.json",
        )
        return not all(path.exists() for path in required)

    def start(self) -> bool:
        """Start Vite development server"""
        if not self.install_dependencies():
            return False

        log_step("Starting Vite dev server...")

        env = dict(subprocess.os.environ)
        env["BUILD_MODE"] = "debug"
        # Always prefer config values over inherited shell env.
        env["VITE_HOST"] = "0.0.0.0"
        env["VITE_PORT"] = str(self.config.serve_port)
        env["VITE_STRICT_PORT"] = "true"
        if self.config.gamepush_enabled:
            env["GAMEPUSH_ENABLED"] = "true"
            if self.config.gp_project_id:
                env["GP_PROJECT_ID"] = self.config.gp_project_id
            if self.config.gp_public_token:
                env["GP_PUBLIC_TOKEN"] = self.config.gp_public_token

        try:
            self._process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=self.ui_dir,
                env=env,
            )
            time.sleep(2)
            exit_code = self._process.poll()
            if exit_code is not None:
                log_error(
                    f"Vite failed to start (exit code {exit_code}). "
                    f"Requested URL: http://localhost:{env['VITE_PORT']}"
                )
                return False
            log_success(f"Vite running: http://localhost:{env['VITE_PORT']} (host={env['VITE_HOST']})")
            return True
        except Exception as e:
            log_error(f"Failed to start Vite: {e}")
            return False

    def stop(self) -> None:
        """Stop Vite server"""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait()
            self._process = None

    def build(self) -> bool:
        """Run Vite production build"""
        if not self.install_dependencies():
            return False

        log_step("Building React UI...")

        env = dict(subprocess.os.environ)
        if self.config.gamepush_enabled:
            env["GAMEPUSH_ENABLED"] = "true"
            if self.config.gp_project_id:
                env["GP_PROJECT_ID"] = self.config.gp_project_id
            if self.config.gp_public_token:
                env["GP_PUBLIC_TOKEN"] = self.config.gp_public_token

        result = run_command(["npm", "run", "build"], cwd=self.ui_dir, env=env)

        if result.success:
            log_success("React UI built successfully")
            return True
        else:
            log_error(f"React build failed: {result.stderr}")
            return False

    @property
    def is_running(self) -> bool:
        """Check if Vite is running"""
        return self._process is not None and self._process.poll() is None

    @property
    def dist_dir(self) -> Path:
        """Get Vite output directory"""
        return self.ui_dir / "dist"
