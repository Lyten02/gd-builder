"""Tests for Haxe service"""

import pytest
from pathlib import Path

from builder.services.haxe import HaxeCompiler


class TestHaxeCompiler:
    """Tests for HaxeCompiler class"""

    def test_generate_hxml_web_debug(self, mock_config):
        """Test hxml generation for web debug"""
        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_hxml("web", "debug")

        assert hxml_path.exists()
        content = hxml_path.read_text()

        assert "-cp src" in content
        assert "-main Main" in content
        assert "-lib heaps" in content
        assert "-js" in content
        assert "debug" in content
        assert "-D source_maps" in content

    def test_generate_hxml_web_release(self, mock_config):
        """Test hxml generation for web release"""
        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_hxml("web", "release")

        content = hxml_path.read_text()

        assert "-dce full" in content
        assert "-D no-traces" in content
        assert "-debug" not in content

    def test_generate_hxml_cpp(self, mock_config):
        """Test hxml generation for cpp"""
        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_hxml("cpp", "debug")

        content = hxml_path.read_text()

        assert "-hl" in content
        assert "game.c" in content

    def test_generate_hxml_gamepush(self, mock_config):
        """Test hxml generation with GamePush"""
        mock_config.gamepush_enabled = True
        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_hxml("web", "debug")

        content = hxml_path.read_text()
        assert "-D gamepush" in content

    def test_hxml_includes_source_paths(self, mock_config, temp_project_dir):
        """Test hxml includes all source paths"""
        # Create additional module
        module_src = temp_project_dir / "modules" / "testmodule" / "src"
        module_src.mkdir(parents=True)

        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_hxml("web", "debug")

        content = hxml_path.read_text()
        assert "-cp src" in content
        assert "testmodule" in content
