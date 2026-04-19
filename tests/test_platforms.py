"""Tests for platform implementations"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestWebPlatform:
    """Tests for WebPlatform"""

    def test_web_platform_name(self, mock_config):
        """Test platform name property"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "debug")
        assert platform.name == "web"

    def test_web_platform_output_dir(self, mock_config):
        """Test output_dir property"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "debug")
        assert platform.output_dir == mock_config.get_web_dir("debug")

    def test_web_platform_prepare_creates_dir(self, mock_config):
        """Test prepare creates web directory"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "debug")
        result = platform.prepare()

        assert result is True
        assert mock_config.get_web_dir("debug").exists()

    def test_create_index_html(self, mock_config):
        """Test index.html creation"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "debug")
        web_dir = mock_config.get_web_dir("debug")
        web_dir.mkdir(parents=True, exist_ok=True)

        index_path = web_dir / "index.html"
        platform._create_index_html(index_path)

        assert index_path.exists()
        content = index_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "game.js" in content
        assert "canvas" in content.lower() or "webgl" in content.lower()

    def test_create_index_html_with_gamepush(self, mock_config):
        """Test index.html includes GamePush when enabled"""
        from builder.platforms.web import WebPlatform

        mock_config.gamepush_enabled = True
        mock_config.gp_project_id = "test_project"
        mock_config.gp_public_token = "test_token"

        platform = WebPlatform(mock_config, "debug")
        web_dir = mock_config.get_web_dir("debug")
        web_dir.mkdir(parents=True, exist_ok=True)

        index_path = web_dir / "index.html"
        platform._create_index_html(index_path)

        content = index_path.read_text()
        assert "gamepush" in content.lower()
        assert "test_project" in content
        assert "test_token" in content

    def test_generate_version_json(self, mock_config):
        """Test version.json generation"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "debug")
        web_dir = mock_config.get_web_dir("debug")
        web_dir.mkdir(parents=True, exist_ok=True)

        platform._generate_version_json()

        version_path = web_dir / "version.json"
        assert version_path.exists()

        # Verify JSON structure
        data = json.loads(version_path.read_text())
        assert "version" in data
        assert "buildTime" in data
        assert "commit" in data

    def test_post_build_copies_resources(self, mock_config):
        """Test post_build copies resources"""
        from builder.platforms.web import WebPlatform

        # Create a resource file
        mock_config.res_dir.mkdir(parents=True, exist_ok=True)
        test_resource = mock_config.res_dir / "test.png"
        test_resource.write_text("fake image data")

        platform = WebPlatform(mock_config, "debug")
        platform.prepare()

        result = platform.post_build()

        assert result is True
        # Check resource was copied
        copied_resource = mock_config.get_web_dir("debug") / "res" / "test.png"
        assert copied_resource.exists()

    def test_post_build_creates_index_html(self, mock_config):
        """Test post_build creates index.html if not exists"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "debug")
        platform.prepare()

        result = platform.post_build()

        assert result is True
        index_path = mock_config.get_web_dir("debug") / "index.html"
        assert index_path.exists()


class TestCppPlatform:
    """Tests for CppPlatform"""

    def test_cpp_platform_name(self, mock_config):
        """Test platform name property"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        assert platform.name == "cpp"

    def test_cpp_platform_output_dir(self, mock_config):
        """Test output_dir property"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        assert platform.output_dir == mock_config.bin_dir / "hlc"

    def test_cpp_platform_binary_path(self, mock_config):
        """Test binary_path property"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        assert platform.binary_path == mock_config.bin_dir / "game"

    def test_cpp_platform_prepare_creates_dir(self, mock_config):
        """Test prepare creates output directory"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        result = platform.prepare()

        assert result is True
        assert platform.output_dir.exists()

    def test_find_makefile_returns_none_when_missing(self, mock_config):
        """Test _find_makefile returns None when no Makefile exists"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        result = platform._find_makefile()

        assert result is None

    def test_find_makefile_in_build_dir(self, mock_config):
        """Test _find_makefile finds Makefile in build directory"""
        from builder.platforms.cpp import CppPlatform

        # Create Makefile in build dir
        makefile = mock_config.build_dir / "Makefile.hlc"
        makefile.write_text("# Makefile")

        platform = CppPlatform(mock_config, "debug")
        result = platform._find_makefile()

        assert result == makefile

    def test_find_makefile_in_starter_dir(self, mock_config):
        """Test _find_makefile finds Makefile in starter directory"""
        from builder.platforms.cpp import CppPlatform

        # Create starter directory with Makefile
        mock_config.starter_dir = mock_config.project_dir / "modules" / "starter"
        tools_dir = mock_config.starter_dir / "tools"
        tools_dir.mkdir(parents=True)
        makefile = tools_dir / "Makefile.hlc"
        makefile.write_text("# Makefile")

        platform = CppPlatform(mock_config, "debug")
        result = platform._find_makefile()

        assert result == makefile

    def test_run_fails_when_binary_missing(self, mock_config):
        """Test run returns False when binary doesn't exist"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        result = platform.run()

        assert result is False

    def test_get_run_command(self, mock_config):
        """Test get_run_command returns binary path"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        cmd = platform.get_run_command()

        assert cmd == [str(mock_config.bin_dir / "game")]

    @patch("builder.platforms.cpp.run_command")
    def test_post_build_fails_without_makefile(self, mock_run, mock_config):
        """Test post_build fails when Makefile is missing"""
        from builder.platforms.cpp import CppPlatform

        platform = CppPlatform(mock_config, "debug")
        platform.prepare()

        result = platform.post_build()

        assert result is False
        mock_run.assert_not_called()


class TestBasePlatform:
    """Tests for BasePlatform abstract class"""

    def test_base_platform_stores_config(self, mock_config):
        """Test BasePlatform stores config and mode"""
        from builder.platforms.web import WebPlatform

        platform = WebPlatform(mock_config, "release")

        assert platform.config == mock_config
        assert platform.mode == "release"
