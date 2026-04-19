"""Integration test fixtures"""

import pytest
import shutil
from pathlib import Path

from builder.config import ProjectConfig, set_config


@pytest.fixture
def haxe_project(tmp_path):
    """Create a minimal Haxe project for integration tests"""
    # src/Main.hx
    src = tmp_path / "src"
    src.mkdir()
    (src / "Main.hx").write_text("""class Main {
    static function main() {
        trace("Hello from integration test!");
    }
}
""")

    # build directory
    build = tmp_path / "build"
    build.mkdir()

    # Create web_debug.hxml
    (build / "web_debug.hxml").write_text("""-cp src
-main Main
-js bin/web/debug/game.js
""")

    # Create web_release.hxml
    (build / "web_release.hxml").write_text("""-cp src
-main Main
-js bin/web/release/game.js
-dce full
""")

    # Required directories
    (tmp_path / "bin" / "web" / "debug").mkdir(parents=True)
    (tmp_path / "bin" / "web" / "release").mkdir(parents=True)
    (tmp_path / "res").mkdir()
    (tmp_path / "modules").mkdir()

    return tmp_path


@pytest.fixture
def haxe_project_config(haxe_project):
    """Create ProjectConfig for integration test project"""
    config = ProjectConfig(
        project_dir=haxe_project,
        src_dir=haxe_project / "src",
        res_dir=haxe_project / "res",
        bin_dir=haxe_project / "bin",
        build_dir=haxe_project / "build",
        modules_dir=haxe_project / "modules",
        ui_dir=haxe_project / "ui",
    )
    set_config(config)
    return config


@pytest.fixture
def haxe_available():
    """Check if Haxe is available, skip test if not"""
    if not shutil.which("haxe"):
        pytest.skip("Haxe not installed")


@pytest.fixture
def node_available():
    """Check if Node.js is available, skip test if not"""
    if not shutil.which("node"):
        pytest.skip("Node.js not installed")


@pytest.fixture
def project_with_syntax_error(haxe_project):
    """Create a project with a syntax error in Main.hx"""
    main_hx = haxe_project / "src" / "Main.hx"
    main_hx.write_text("""class Main {
    static function main() {
        // Syntax error: missing semicolon and invalid keyword
        trace("Hello"
        invalid_keyword
    }
}
""")
    return haxe_project


@pytest.fixture
def project_with_multiple_files(haxe_project):
    """Create a project with multiple source files"""
    src = haxe_project / "src"

    # Create additional source files
    (src / "Utils.hx").write_text("""class Utils {
    public static function greet(name:String):String {
        return "Hello, " + name + "!";
    }
}
""")

    # Update Main.hx to use Utils
    (src / "Main.hx").write_text("""class Main {
    static function main() {
        trace(Utils.greet("World"));
    }
}
""")

    return haxe_project
