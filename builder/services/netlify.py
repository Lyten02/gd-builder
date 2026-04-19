"""Netlify deployment service"""

import json
import subprocess
import tempfile
from pathlib import Path

from ..config import ProjectConfig
from ..utils.logger import log_step, log_success, log_error, log_info
from ..utils.process import run_command


def deploy_netlify(config: ProjectConfig, publish_dir: Path) -> bool:
    """Deploy to Netlify"""

    if not config.netlify_token:
        log_error("NETLIFY_TOKEN not found in .env")
        log_info("Generate token at: https://app.netlify.com/user/applications#personal-access-tokens")
        return False

    # Create zip
    zip_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    zip_path = Path(zip_file.name)
    zip_file.close()

    log_step("Creating deployment archive...")
    run_command(
        ["zip", "-r", str(zip_path), ".", "-x", "*.DS_Store"],
        cwd=publish_dir,
    )

    try:
        if config.netlify_site_id:
            return _deploy_to_existing_site(config, zip_path)
        else:
            return _create_new_site(config, zip_path)
    finally:
        zip_path.unlink(missing_ok=True)


def _deploy_to_existing_site(config: ProjectConfig, zip_path: Path) -> bool:
    """Deploy to existing Netlify site"""
    log_step("Deploying to existing site...")

    result = subprocess.run(
        [
            "curl", "-s",
            "-H", f"Authorization: Bearer {config.netlify_token}",
            "-H", "Content-Type: application/zip",
            "--data-binary", f"@{zip_path}",
            f"https://api.netlify.com/api/v1/sites/{config.netlify_site_id}/deploys?production=true",
        ],
        capture_output=True,
        text=True,
    )

    try:
        response = json.loads(result.stdout)
        site_url = response.get("ssl_url")
        if site_url:
            log_success(f"Deployed: {site_url}")
            return True
        else:
            log_error(f"Deploy failed. Response: {result.stdout}")
            return False
    except json.JSONDecodeError:
        log_error(f"Invalid response: {result.stdout}")
        return False


def _create_new_site(config: ProjectConfig, zip_path: Path) -> bool:
    """Create new Netlify site"""
    log_step("Creating new Netlify site...")

    result = subprocess.run(
        [
            "curl", "-s",
            "-H", f"Authorization: Bearer {config.netlify_token}",
            "-H", "Content-Type: application/zip",
            "--data-binary", f"@{zip_path}",
            "https://api.netlify.com/api/v1/sites",
        ],
        capture_output=True,
        text=True,
    )

    try:
        response = json.loads(result.stdout)
        site_id = response.get("id")
        site_url = response.get("ssl_url")

        if site_id:
            # Save site_id to .env
            env_file = config.project_dir / ".env"
            with open(env_file, "a") as f:
                f.write(f"\nNETLIFY_SITE_ID={site_id}\n")

            log_success(f"Site created: {site_url}")
            log_info(f"Site ID saved to .env: {site_id}")
            return True
        else:
            log_error(f"Failed to create site. Response: {result.stdout}")
            return False
    except json.JSONDecodeError:
        log_error(f"Invalid response: {result.stdout}")
        return False


def deploy_netlify_watch(config: ProjectConfig) -> bool:
    """Quick deploy for watch mode"""

    if not config.netlify_token or not config.netlify_site_id:
        return False

    web_dir = config.get_web_dir("debug")

    # Create temp zip
    zip_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    zip_path = Path(zip_file.name)
    zip_file.close()

    run_command(
        ["zip", "-rq", str(zip_path), ".", "-x", "*.DS_Store", "-x", ".buildtime"],
        cwd=web_dir,
    )

    try:
        result = subprocess.run(
            [
                "curl", "-s",
                "-H", f"Authorization: Bearer {config.netlify_token}",
                "-H", "Content-Type: application/zip",
                "--data-binary", f"@{zip_path}",
                f"https://api.netlify.com/api/v1/sites/{config.netlify_site_id}/deploys?production=true",
            ],
            capture_output=True,
            text=True,
        )

        response = json.loads(result.stdout)
        deploy_url = response.get("ssl_url")
        if deploy_url:
            log_success(f"Deployed: {deploy_url}")
            return True
        return False
    except Exception:
        return False
    finally:
        zip_path.unlink(missing_ok=True)
