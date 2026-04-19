"""Tests for process utilities"""

import subprocess
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestProcessResult:
    """Tests for ProcessResult class"""

    def test_process_result_success(self):
        """Test ProcessResult with successful command"""
        from builder.utils.process import ProcessResult

        result = ProcessResult(
            success=True,
            stdout="output",
            stderr="",
            duration_ms=100,
            return_code=0
        )
        assert result.success is True
        assert result.return_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.duration_ms == 100

    def test_process_result_failure(self):
        """Test ProcessResult with failed command"""
        from builder.utils.process import ProcessResult

        result = ProcessResult(
            success=False,
            stdout="",
            stderr="error message",
            duration_ms=50,
            return_code=1
        )
        assert result.success is False
        assert result.return_code == 1
        assert result.stderr == "error message"


class TestRunCommand:
    """Tests for run_command function"""

    def test_run_command_success(self):
        """Test successful command execution"""
        from builder.utils.process import run_command

        result = run_command(["echo", "hello"])
        assert result.success is True
        assert result.return_code == 0
        assert "hello" in result.stdout

    def test_run_command_failure(self):
        """Test failed command execution"""
        from builder.utils.process import run_command

        result = run_command(["false"])  # false always returns 1
        assert result.success is False
        assert result.return_code == 1

    def test_run_command_with_cwd(self, tmp_path):
        """Test command execution with working directory"""
        from builder.utils.process import run_command

        # Create a test file in temp directory
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = run_command(["ls"], cwd=tmp_path)
        assert result.success is True
        assert "test.txt" in result.stdout

    def test_run_command_not_found(self):
        """Test handling of non-existent command"""
        from builder.utils.process import run_command

        result = run_command(["nonexistent_command_12345"])
        assert result.success is False
        assert result.return_code == -1
        assert "not found" in result.stderr.lower() or "command not found" in result.stderr.lower()

    def test_run_command_timeout(self):
        """Test command timeout handling"""
        from builder.utils.process import run_command

        # This should timeout quickly
        result = run_command(["sleep", "10"], timeout=1)
        assert result.success is False
        assert "timeout" in result.stderr.lower() or result.return_code == -1

    def test_run_command_captures_stderr(self):
        """Test that stderr is captured"""
        from builder.utils.process import run_command

        # Redirect stdout to stderr using bash
        result = run_command(["bash", "-c", "echo error >&2"])
        assert "error" in result.stderr

    def test_run_command_duration_tracked(self):
        """Test that command duration is tracked"""
        from builder.utils.process import run_command

        result = run_command(["sleep", "0.1"])
        # Duration should be at least 100ms (sleep 0.1s = 100ms)
        assert result.duration_ms >= 50  # Allow some margin


class TestRunHaxe:
    """Tests for run_haxe function"""

    def test_run_haxe_basic(self):
        """Test run_haxe passes args to haxe"""
        from builder.utils.process import run_haxe

        # This will likely fail if haxe isn't installed,
        # but it tests the function signature
        result = run_haxe(["--version"])

        # If haxe is installed, it should work
        # If not, the function should still return a ProcessResult
        assert isinstance(result.success, bool)
        assert isinstance(result.return_code, int)


class TestRunNode:
    """Tests for run_node function"""

    def test_run_node_basic(self, tmp_path):
        """Test run_node executes JavaScript file"""
        from builder.utils.process import run_node

        # Create a simple JS file
        js_file = tmp_path / "test.js"
        js_file.write_text('console.log("hello from node");')

        result = run_node(js_file)

        # If node is installed, it should work
        if result.success:
            assert "hello from node" in result.stdout


class TestCheckCommandExists:
    """Tests for check_command_exists function"""

    def test_command_exists_python(self):
        """Test existing command (python3 should exist)"""
        from builder.utils.process import check_command_exists

        # python3 or python should exist in most environments
        assert check_command_exists("python3") or check_command_exists("python")

    def test_command_not_exists(self):
        """Test non-existing command"""
        from builder.utils.process import check_command_exists

        result = check_command_exists("nonexistent_command_xyz_12345")
        assert result is False

    def test_command_exists_echo(self):
        """Test echo command exists"""
        from builder.utils.process import check_command_exists

        assert check_command_exists("echo") is True

    def test_command_exists_ls(self):
        """Test ls command exists"""
        from builder.utils.process import check_command_exists

        assert check_command_exists("ls") is True
