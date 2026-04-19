"""Development HTTP server"""

import subprocess
from pathlib import Path
from typing import Optional

from ..utils.logger import log_success, log_error


class DevServer:
    """Simple HTTP server for development"""

    def __init__(self, port: int = 5500):
        self.port = port
        self._process: Optional[subprocess.Popen] = None

    def start(self, directory: Path) -> bool:
        """Start the server"""
        try:
            self._process = subprocess.Popen(
                ["python3", "-m", "http.server", str(self.port)],
                cwd=directory,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log_success(f"Server running: http://localhost:{self.port}")
            return True
        except Exception as e:
            log_error(f"Failed to start server: {e}")
            return False

    def stop(self) -> None:
        """Stop the server"""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process.wait()
            self._process = None

    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._process is not None and self._process.poll() is None
