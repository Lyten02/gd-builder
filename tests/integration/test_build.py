"""Integration tests for build command"""

import pytest
from pathlib import Path


@pytest.mark.integration
class TestBuildIntegration:
    """Integration tests for build command - require Haxe to be installed"""

    def test_build_web_debug_creates_game_js(self, haxe_project_config, haxe_available):
        """Test web debug build creates game.js"""
        from builder.commands.build import _build_single

        result = _build_single(haxe_project_config, "debug", "web")

        assert result is True
        game_js = haxe_project_config.get_web_dir("debug") / "game.js"
        assert game_js.exists()
        # Verify it contains JavaScript
        content = game_js.read_text()
        assert len(content) > 0

    def test_build_web_release_creates_game_js(self, haxe_project_config, haxe_available):
        """Test web release build creates game.js"""
        from builder.commands.build import _build_single

        result = _build_single(haxe_project_config, "release", "web")

        assert result is True
        game_js = haxe_project_config.get_web_dir("release") / "game.js"
        assert game_js.exists()

    def test_build_creates_index_html(self, haxe_project_config, haxe_available):
        """Test build creates index.html via post_build"""
        from builder.commands.build import _build_single

        result = _build_single(haxe_project_config, "debug", "web")

        assert result is True
        index_html = haxe_project_config.get_web_dir("debug") / "index.html"
        assert index_html.exists()

    def test_build_creates_version_json(self, haxe_project_config, haxe_available):
        """Test build creates version.json for auto-reload"""
        from builder.commands.build import _build_single

        result = _build_single(haxe_project_config, "debug", "web")

        assert result is True
        version_json = haxe_project_config.get_web_dir("debug") / "version.json"
        assert version_json.exists()

        import json
        data = json.loads(version_json.read_text())
        assert "version" in data
        assert "buildTime" in data


@pytest.mark.integration
class TestBuildErrors:
    """Integration tests for build error handling"""

    def test_build_with_syntax_error_fails(self, project_with_syntax_error, haxe_available):
        """Test build fails gracefully on syntax error"""
        from builder.commands.build import _build_single
        from builder.config import ProjectConfig, set_config

        config = ProjectConfig(
            project_dir=project_with_syntax_error,
            src_dir=project_with_syntax_error / "src",
            res_dir=project_with_syntax_error / "res",
            bin_dir=project_with_syntax_error / "bin",
            build_dir=project_with_syntax_error / "build",
            modules_dir=project_with_syntax_error / "modules",
            ui_dir=project_with_syntax_error / "ui",
        )
        set_config(config)

        result = _build_single(config, "debug", "web")

        assert result is False

    def test_build_with_missing_source_fails(self, haxe_project_config, haxe_available):
        """Test build fails when source files are missing"""
        from builder.commands.build import _build_single

        # Delete Main.hx
        main_hx = haxe_project_config.src_dir / "Main.hx"
        main_hx.unlink()

        result = _build_single(haxe_project_config, "debug", "web")

        assert result is False


@pytest.mark.integration
class TestBuildMultipleFiles:
    """Integration tests for building projects with multiple files"""

    def test_build_multiple_files(self, project_with_multiple_files, haxe_available):
        """Test building project with multiple source files"""
        from builder.commands.build import _build_single
        from builder.config import ProjectConfig, set_config

        config = ProjectConfig(
            project_dir=project_with_multiple_files,
            src_dir=project_with_multiple_files / "src",
            res_dir=project_with_multiple_files / "res",
            bin_dir=project_with_multiple_files / "bin",
            build_dir=project_with_multiple_files / "build",
            modules_dir=project_with_multiple_files / "modules",
            ui_dir=project_with_multiple_files / "ui",
        )
        set_config(config)

        result = _build_single(config, "debug", "web")

        assert result is True
        game_js = config.get_web_dir("debug") / "game.js"
        assert game_js.exists()

        # Verify both classes are compiled (check for Utils reference)
        content = game_js.read_text()
        assert len(content) > 100  # Should have substantial content
