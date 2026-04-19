"""Pytest configuration and fixtures"""

import tempfile
from pathlib import Path
import pytest

from builder.config import ProjectConfig, set_config


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create basic structure
        (project_dir / "src").mkdir()
        (project_dir / "res").mkdir()
        (project_dir / "build").mkdir()
        (project_dir / "modules").mkdir()

        # Create a simple Main.hx
        (project_dir / "src" / "Main.hx").write_text("""
class Main extends hxd.App {
    override function init() {
        trace("Hello!");
    }
    static function main() {
        new Main();
    }
}
""")

        yield project_dir


@pytest.fixture
def mock_config(temp_project_dir):
    """Create a mock ProjectConfig"""
    config = ProjectConfig(
        project_dir=temp_project_dir,
        src_dir=temp_project_dir / "src",
        res_dir=temp_project_dir / "res",
        bin_dir=temp_project_dir / "bin",
        build_dir=temp_project_dir / "build",
        modules_dir=temp_project_dir / "modules",
        ui_dir=temp_project_dir / "ui",
    )
    set_config(config)
    return config
