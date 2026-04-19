"""Build command implementation"""

from ..config import ProjectConfig
from ..services.haxe import build_platform
from ..platforms.web import WebPlatform
from ..platforms.cpp import CppPlatform
from ..utils.logger import log_info, log_error, log_success


def build_command(config: ProjectConfig, mode: str, platform: str) -> bool:
    """Build the project for specified platform(s)"""

    if platform == "all":
        return _build_all(config, mode)

    return _build_single(config, mode, platform)


def _build_single(config: ProjectConfig, mode: str, platform: str) -> bool:
    """Build single platform"""

    # Validate GamePush config if enabled
    if config.gamepush_enabled and platform == "web":
        if not config.validate_gamepush():
            log_error("GP_PROJECT_ID and GP_PUBLIC_TOKEN required for --gamepush builds")
            log_info("Add them to .env file:")
            log_info("  GP_PROJECT_ID=your_project_id")
            log_info("  GP_PUBLIC_TOKEN=your_public_token")
            return False

    # Get platform instance
    if platform == "web":
        plat = WebPlatform(config, mode)
    elif platform == "cpp":
        plat = CppPlatform(config, mode)
    else:
        log_error(f"Unknown platform: {platform}")
        return False

    # Prepare
    plat.prepare()

    # Build Haxe
    result = build_platform(config, platform, mode)
    if not result.success:
        return False

    # Post-build (copy resources, etc)
    if not plat.post_build():
        return False

    return True


def _build_all(config: ProjectConfig, mode: str) -> bool:
    """Build all platforms"""
    platforms = ["web", "cpp"]
    failed = []

    log_info(f"Building all: {', '.join(platforms)}")

    for platform in platforms:
        if not _build_single(config, mode, platform):
            failed.append(platform)

    if failed:
        log_error(f"Failed platforms: {', '.join(failed)}")
        return False

    log_success("All platforms built successfully!")
    return True
