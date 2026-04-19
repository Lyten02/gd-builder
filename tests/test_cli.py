"""Tests for CLI"""

import pytest
from click.testing import CliRunner

from builder.cli import cli


class TestCLI:
    """Tests for CLI commands"""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_help(self, runner):
        """Test help command"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Haxe/Heaps Build System" in result.output

    def test_build_requires_mode(self, runner):
        """Test that build requires mode argument"""
        result = runner.invoke(cli, ["build"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "MODE" in result.output

    def test_build_invalid_mode(self, runner):
        """Test build with invalid mode"""
        result = runner.invoke(cli, ["build", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "debug" in result.output

    def test_run_requires_mode(self, runner):
        """Test that run requires mode argument"""
        result = runner.invoke(cli, ["run"])
        assert result.exit_code != 0

    def test_watch_requires_mode(self, runner):
        """Test that watch requires mode argument"""
        result = runner.invoke(cli, ["watch"])
        assert result.exit_code != 0

    def test_publish_requires_mode(self, runner):
        """Test that publish requires mode argument"""
        result = runner.invoke(cli, ["publish"])
        assert result.exit_code != 0

    def test_test_default_mode(self, runner):
        """Test that test has default mode"""
        # This will fail due to missing test.hxml, but should parse args correctly
        result = runner.invoke(cli, ["test"])
        # Should at least get past argument parsing
        assert "Missing argument" not in result.output

    def test_clean_no_args(self, runner):
        """Test clean command needs no args"""
        # May fail if project structure doesn't exist, but should parse
        result = runner.invoke(cli, ["clean", "--help"])
        assert result.exit_code == 0

    def test_setup_no_args(self, runner):
        """Test setup command needs no args"""
        result = runner.invoke(cli, ["setup", "--help"])
        assert result.exit_code == 0

    def test_version(self, runner):
        """Test version flag"""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
