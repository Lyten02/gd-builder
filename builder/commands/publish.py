"""Publish command implementation"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from ..config import ProjectConfig
from ..commands.build import _build_single
from ..platforms.web import WebPlatform
from ..services.haxe import build_platform, HaxeCompiler
from ..utils.logger import log_step, log_success, log_error, log_info
from ..utils.path import path_for_project
from ..utils.process import run_command


def publish_command(config: ProjectConfig, mode: str, platform: str) -> bool:
    """Create release build and package"""

    if platform == "all":
        return _publish_all(config, mode)

    return _publish_single(config, mode, platform)


def _publish_single(config: ProjectConfig, mode: str, platform: str) -> bool:
    """Publish single platform"""

    # Determine publish directory
    suffix = "-gamepush" if config.gamepush_enabled else ""
    publish_dir = config.project_dir / "publish" / f"{platform}{suffix}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    publish_dir.mkdir(parents=True, exist_ok=True)

    log_step(f"Publishing {platform}{suffix}...")

    if platform == "web":
        return _publish_web(config, mode, publish_dir, timestamp)
    elif platform == "cpp":
        return _publish_cpp(config, mode, publish_dir, timestamp)
    else:
        log_error(f"Unknown platform: {platform}")
        return False


def _publish_web(config: ProjectConfig, mode: str, publish_dir: Path, timestamp: str) -> bool:
    """Publish web build"""

    # React mode
    if config.react_mode:
        return _publish_react(config, mode, publish_dir, timestamp)

    # Standard Heaps mode
    if not _build_single(config, mode, "web"):
        return False

    web_dir = config.get_web_dir(mode)

    # Copy files
    game_js = web_dir / "game.js"
    index_html = web_dir / "index.html"

    if game_js.exists():
        shutil.copy(game_js, publish_dir / "game.js")
    if index_html.exists():
        shutil.copy(index_html, publish_dir / "index.html")

    # Copy resources
    res_dir = web_dir / "res"
    if res_dir.exists():
        shutil.copytree(res_dir, publish_dir / "res", dirs_exist_ok=True)

    # Generate version.json
    plat = WebPlatform(config, mode)
    plat._generate_version_json()
    shutil.copy(web_dir / "version.json", publish_dir / "version.json")

    # Create zip
    zip_name = f"{config.project_name}_web{'-gamepush' if config.gamepush_enabled else ''}_{timestamp}.zip"
    _create_zip(publish_dir, config.project_dir / "publish" / zip_name)

    # Deploy to Netlify if requested
    if config.netlify_deploy:
        _deploy_netlify(config, publish_dir)

    log_success(f"Published to {publish_dir}")
    return True


def _publish_react(config: ProjectConfig, mode: str, publish_dir: Path, timestamp: str) -> bool:
    """Publish React + Haxe build"""

    log_info("Building React UI + Haxe API...")

    # Build Haxe
    if not _build_single(config, mode, "web"):
        return False

    # Build React
    ui_dir = config.ui_dir
    if not ui_dir.exists():
        log_error(f"React UI directory not found: {ui_dir}")
        return False

    env = dict(os.environ)
    if config.gamepush_enabled:
        env["GAMEPUSH_ENABLED"] = "true"

    result = run_command(["npm", "run", "build"], cwd=ui_dir, env=env)
    if not result.success:
        error_detail = result.stderr or result.stdout or "Unknown error"
        log_error(f"React build failed:\n{error_detail}")
        return False

    vite_dist = ui_dir / "dist"
    if not vite_dist.exists():
        log_error("Vite build failed - dist directory not found")
        return False

    # Remove watch folder from dist
    watch_dir = vite_dist / "watch"
    if watch_dir.exists():
        shutil.rmtree(watch_dir)

    # Copy Haxe files to dist
    web_dir = config.get_web_dir(mode)
    game_js = web_dir / "game.js"
    if game_js.exists():
        shutil.copy(game_js, vite_dist / "game.js")

    # Build release API
    log_info("Building release API...")
    starter_src = config.project_dir / "modules" / "haxeheaps-starter" / "src"
    if config.starter_dir and (config.starter_dir / "src").exists():
        starter_src = config.starter_dir / "src"

    api_result = run_command([
        "haxe",
        "-cp", "src",
        "-cp", path_for_project(starter_src, config.project_dir),
        "-main", "bridge.Api",
        "-js", str(vite_dist / "quickpaint.js"),
        "-D", "js-es=6",
        "-dce", "full",
    ], cwd=config.project_dir)

    if not api_result.success:
        log_error(f"API build failed: {api_result.stderr}")
        return False

    # Copy to publish dir
    shutil.copytree(vite_dist, publish_dir, dirs_exist_ok=True)

    # Create zip
    zip_name = f"{config.project_name}_web{'-gamepush' if config.gamepush_enabled else ''}_{timestamp}.zip"
    _create_zip(publish_dir, config.project_dir / "publish" / zip_name)

    if config.netlify_deploy:
        _deploy_netlify(config, publish_dir)

    log_success(f"Published to {publish_dir}")
    return True


def _publish_cpp(config: ProjectConfig, mode: str, publish_dir: Path, timestamp: str) -> bool:
    """Publish C++ build"""

    if not _build_single(config, mode, "cpp"):
        return False

    binary = config.bin_dir / "game"
    if binary.exists():
        shutil.copy(binary, publish_dir / config.project_name)

    # Copy resources
    if config.res_dir.exists():
        shutil.copytree(config.res_dir, publish_dir / "res", dirs_exist_ok=True)

    # Create tar.gz
    tar_name = f"{config.project_name}_cpp_{timestamp}.tar.gz"
    run_command(
        ["tar", "-czf", tar_name, "cpp"],
        cwd=config.project_dir / "publish",
    )

    log_success(f"Published to {publish_dir}")
    return True


def _publish_all(config: ProjectConfig, mode: str) -> bool:
    """Publish all platforms"""
    for platform in ["web", "cpp"]:
        if not _publish_single(config, mode, platform):
            return False
    return True


def _create_zip(source_dir: Path, zip_path: Path) -> None:
    """Create zip archive"""
    run_command(
        ["zip", "-r", str(zip_path), ".", "-x", "*.DS_Store"],
        cwd=source_dir,
    )


def _deploy_netlify(config: ProjectConfig, publish_dir: Path) -> bool:
    """Deploy to Netlify"""
    from ..services.netlify import deploy_netlify
    return deploy_netlify(config, publish_dir)
