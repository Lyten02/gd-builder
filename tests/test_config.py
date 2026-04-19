"""Tests for ProjectConfig"""

import pytest
from pathlib import Path

from builder.config import ProjectConfig


class TestProjectConfig:
    """Tests for ProjectConfig class"""

    def test_source_paths_basic(self, mock_config):
        """Test basic source path detection"""
        paths = mock_config.get_source_paths()
        assert mock_config.src_dir in paths

    def test_web_dir_debug(self, mock_config):
        """Test web dir path for debug mode"""
        web_dir = mock_config.get_web_dir("debug")
        assert "debug" in str(web_dir)
        assert "gamepush" not in str(web_dir)

    def test_web_dir_release(self, mock_config):
        """Test web dir path for release mode"""
        web_dir = mock_config.get_web_dir("release")
        assert "release" in str(web_dir)

    def test_web_dir_gamepush(self, mock_config):
        """Test web dir path with GamePush enabled"""
        mock_config.gamepush_enabled = True
        web_dir = mock_config.get_web_dir("debug")
        assert "gamepush" in str(web_dir)

    def test_hxml_path(self, mock_config):
        """Test hxml file path generation"""
        hxml_path = mock_config.get_hxml_path("web", "debug")
        assert hxml_path.name == "web_debug.hxml"
        assert hxml_path.parent == mock_config.build_dir

    def test_validate_gamepush_disabled(self, mock_config):
        """Test GamePush validation when disabled"""
        mock_config.gamepush_enabled = False
        assert mock_config.validate_gamepush() is True

    def test_validate_gamepush_missing_config(self, mock_config):
        """Test GamePush validation with missing config"""
        mock_config.gamepush_enabled = True
        mock_config.gp_project_id = None
        mock_config.gp_public_token = None
        assert mock_config.validate_gamepush() is False

    def test_validate_gamepush_complete(self, mock_config):
        """Test GamePush validation with complete config"""
        mock_config.gamepush_enabled = True
        mock_config.gp_project_id = "test_id"
        mock_config.gp_public_token = "test_token"
        assert mock_config.validate_gamepush() is True

    def test_validate_netlify_disabled(self, mock_config):
        """Test Netlify validation when disabled"""
        mock_config.netlify_deploy = False
        assert mock_config.validate_netlify() is True

    def test_validate_netlify_missing_token(self, mock_config):
        """Test Netlify validation with missing token"""
        mock_config.netlify_deploy = True
        mock_config.netlify_token = None
        assert mock_config.validate_netlify() is False

    def test_serve_port_reads_vite_port_from_env(self, temp_project_dir, monkeypatch):
        """Use VITE_PORT from env when SERVE_PORT is not set"""
        monkeypatch.delenv("SERVE_PORT", raising=False)
        monkeypatch.setenv("VITE_PORT", "6123")
        config = ProjectConfig.from_project_root(temp_project_dir)
        assert config.serve_port == 6123

    def test_serve_port_prefers_serve_port_over_vite_port(self, temp_project_dir, monkeypatch):
        """SERVE_PORT should have precedence over VITE_PORT"""
        monkeypatch.setenv("SERVE_PORT", "7001")
        monkeypatch.setenv("VITE_PORT", "6123")
        config = ProjectConfig.from_project_root(temp_project_dir)
        assert config.serve_port == 7001


class TestConfigPaths:
    """Tests for path-related functionality"""

    def test_source_paths_with_starter(self, temp_project_dir, mock_config):
        """Test source paths include starter module"""
        # Create starter module
        starter_dir = temp_project_dir / "modules" / "starter" / "src"
        starter_dir.mkdir(parents=True)

        mock_config.starter_dir = temp_project_dir / "modules" / "starter"
        paths = mock_config.get_source_paths()

        assert mock_config.starter_dir / "src" in paths

    def test_source_paths_with_custom_modules(self, temp_project_dir, mock_config):
        """Test source paths include custom modules"""
        # Create custom module
        custom_module = temp_project_dir / "modules" / "mymodule" / "src"
        custom_module.mkdir(parents=True)

        paths = mock_config.get_source_paths()

        assert custom_module in paths
