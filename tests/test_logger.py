"""Tests for logger utilities"""

import pytest
from io import StringIO
from unittest.mock import patch, MagicMock


class TestLogger:
    """Tests for logging functions"""

    def test_log_info_outputs_message(self, capsys):
        """Test log_info outputs the message"""
        from builder.utils.logger import log_info

        log_info("Test message")
        captured = capsys.readouterr()
        assert "Test message" in captured.out

    def test_log_success_outputs_message(self, capsys):
        """Test log_success outputs the message"""
        from builder.utils.logger import log_success

        log_success("Success!")
        captured = capsys.readouterr()
        assert "Success!" in captured.out

    def test_log_error_outputs_message(self, capsys):
        """Test log_error outputs the message"""
        from builder.utils.logger import log_error

        log_error("Error!")
        captured = capsys.readouterr()
        # Rich may output to stdout even for errors
        assert "Error!" in captured.out or "Error!" in captured.err

    def test_log_step_outputs_message(self, capsys):
        """Test log_step outputs the message"""
        from builder.utils.logger import log_step

        log_step("Step 1")
        captured = capsys.readouterr()
        assert "Step 1" in captured.out

    def test_log_warn_outputs_message(self, capsys):
        """Test log_warn outputs the message"""
        from builder.utils.logger import log_warn

        log_warn("Warning!")
        captured = capsys.readouterr()
        assert "Warning!" in captured.out

    def test_log_time_outputs_timing(self, capsys):
        """Test log_time outputs timing info"""
        from builder.utils.logger import log_time

        log_time("Build", 1234)
        captured = capsys.readouterr()
        assert "Build" in captured.out
        assert "1234" in captured.out

    def test_log_paths_outputs_project_dir(self, capsys):
        """Test log_paths outputs project directory"""
        from builder.utils.logger import log_paths

        log_paths("/test/project")
        captured = capsys.readouterr()
        assert "/test/project" in captured.out

    def test_log_paths_outputs_starter_dir(self, capsys):
        """Test log_paths outputs starter directory when provided"""
        from builder.utils.logger import log_paths

        log_paths("/test/project", "/test/starter")
        captured = capsys.readouterr()
        assert "/test/project" in captured.out
        assert "/test/starter" in captured.out

    def test_log_info_contains_tag(self, capsys):
        """Test log_info contains INFO tag"""
        from builder.utils.logger import log_info

        log_info("Test")
        captured = capsys.readouterr()
        assert "INFO" in captured.out

    def test_log_success_contains_tag(self, capsys):
        """Test log_success contains SUCCESS tag"""
        from builder.utils.logger import log_success

        log_success("Test")
        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out

    def test_log_warn_contains_tag(self, capsys):
        """Test log_warn contains WARN tag"""
        from builder.utils.logger import log_warn

        log_warn("Test")
        captured = capsys.readouterr()
        assert "WARN" in captured.out

    def test_log_error_contains_tag(self, capsys):
        """Test log_error contains ERROR tag"""
        from builder.utils.logger import log_error

        log_error("Test")
        captured = capsys.readouterr()
        # Check both streams as Rich behavior may vary
        output = captured.out + captured.err
        assert "ERROR" in output

    def test_log_step_contains_tag(self, capsys):
        """Test log_step contains STEP tag"""
        from builder.utils.logger import log_step

        log_step("Test")
        captured = capsys.readouterr()
        assert "STEP" in captured.out
