"""Run command implementation"""

from ..config import ProjectConfig
from ..commands.build import _build_single
from ..platforms.web import WebPlatform
from ..platforms.cpp import CppPlatform
from ..utils.logger import log_error


def run_command(config: ProjectConfig, mode: str, platform: str) -> bool:
    """Build and run the project"""

    # Build first
    if not _build_single(config, mode, platform):
        return False

    # Get platform instance
    if platform == "web":
        plat = WebPlatform(config, mode)
    elif platform == "cpp":
        plat = CppPlatform(config, mode)
    else:
        log_error(f"Cannot run platform: {platform}")
        return False

    # Run
    return plat.run()
