"""Base platform abstraction"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..config import ProjectConfig


class BasePlatform(ABC):
    """Abstract base class for build platforms"""

    def __init__(self, config: ProjectConfig, mode: str):
        self.config = config
        self.mode = mode

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform name (web, cpp, etc)"""
        pass

    @property
    @abstractmethod
    def output_dir(self) -> Path:
        """Output directory for build artifacts"""
        pass

    @abstractmethod
    def prepare(self) -> bool:
        """Prepare build environment (create dirs, etc)"""
        pass

    @abstractmethod
    def post_build(self) -> bool:
        """Post-build actions (copy resources, generate index.html, etc)"""
        pass

    def run(self) -> bool:
        """Run the built application"""
        raise NotImplementedError(f"Run not implemented for {self.name}")

    def get_run_command(self) -> Optional[list[str]]:
        """Get command to run the application"""
        return None
