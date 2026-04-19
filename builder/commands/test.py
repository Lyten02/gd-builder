"""Test command implementation"""

from pathlib import Path

from ..config import ProjectConfig
from ..services.haxe import build_test
from ..utils.logger import log_step, log_success, log_error, log_info
from ..utils.process import run_command as run_cmd, run_node, check_command_exists


def test_command(config: ProjectConfig) -> bool:
    """Run Haxe tests"""

    log_step("Running tests...")

    # Check test.hxml exists
    test_hxml = config.build_dir / "test.hxml"
    if not test_hxml.exists():
        log_error(f"test.hxml not found at {test_hxml}")
        log_info("Create test.hxml and test files first")
        return False

    # Check utest is installed
    result = run_cmd(["haxelib", "path", "utest"])
    if not result.success:
        log_info("Installing utest...")
        install_result = run_cmd(["haxelib", "install", "utest"])
        if not install_result.success:
            log_error("Failed to install utest")
            return False

    # Compile tests
    compile_result = build_test(config)
    if not compile_result.success:
        log_error(f"Test compilation failed: {compile_result.error_message}")
        return False

    log_success(f"Tests compiled in {compile_result.duration_ms}ms")

    # Run tests with Node.js
    if not check_command_exists("node"):
        log_error("Node.js not found. Install it to run tests.")
        return False

    test_js = config.bin_dir / "test" / "test.js"
    if not test_js.exists():
        log_error(f"Test output not found: {test_js}")
        return False

    log_step("Executing tests...")
    run_result = run_node(test_js, cwd=config.project_dir)

    if run_result.stdout:
        print(run_result.stdout)
    if run_result.stderr:
        print(run_result.stderr)

    if run_result.success:
        log_success("All tests passed!")
        return True
    else:
        log_error("Some tests failed")
        return False
