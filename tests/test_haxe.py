"""Tests for Haxe service"""

from builder.services.haxe import HaxeCompiler
from builder.commands.setup import _setup_haxe_libs


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

    def test_generate_hxml_includes_profile_and_module_libs(self, mock_config, temp_project_dir):
        """Test hxml includes project profile libs and module-declared libs."""
        profile_dir = temp_project_dir / "build" / "profiles"
        profile_dir.mkdir(parents=True)
        (profile_dir / "main.json").write_text(
            '{"libs": ["heaps:git", "domkit"]}',
            encoding="utf-8",
        )

        module_dir = temp_project_dir / "modules" / "testmodule"
        module_dir.mkdir()
        (module_dir / "module.json").write_text(
            '{"libs": ["heaps", "deepnightLibs"]}',
            encoding="utf-8",
        )

        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_hxml("web", "debug")

        lib_lines = [
            line for line in hxml_path.read_text().splitlines()
            if line.startswith("-lib ")
        ]
        assert lib_lines == [
            "-lib heaps:git",
            "-lib domkit",
            "-lib deepnightLibs",
        ]

    def test_generate_test_hxml_includes_project_and_module_tests(
        self, mock_config, temp_project_dir
    ):
        """Test test.hxml covers project tests, module tests, and declared libs."""
        profile_dir = temp_project_dir / "build" / "profiles"
        profile_dir.mkdir(parents=True)
        (profile_dir / "main.json").write_text(
            '{"libs": ["heaps:git", "domkit"]}',
            encoding="utf-8",
        )

        (temp_project_dir / "test").mkdir()
        module_dir = temp_project_dir / "modules" / "testmodule"
        (module_dir / "src").mkdir(parents=True)
        (module_dir / "test").mkdir()
        (module_dir / "module.json").write_text(
            '{"libs": ["deepnightLibs"]}',
            encoding="utf-8",
        )
        builder_haxe = temp_project_dir / "modules" / "gd-builder" / "haxe"
        builder_haxe.mkdir(parents=True)

        compiler = HaxeCompiler(mock_config)
        hxml_path = compiler.generate_test_hxml()

        lines = hxml_path.read_text().splitlines()
        assert f"-cp {str((temp_project_dir / 'src').relative_to(temp_project_dir))}" in lines
        assert "-cp test" in lines
        assert f"-cp {str(builder_haxe.relative_to(temp_project_dir))}" in lines
        assert f"-cp {str((module_dir / 'test').relative_to(temp_project_dir))}" in lines
        assert "-lib utest" in lines
        assert "-lib hxnodejs" in lines
        assert "-lib heaps:git" in lines
        assert "-lib domkit" in lines
        assert "-lib deepnightLibs" in lines

    def test_setup_haxe_libs_installs_profile_and_module_libs(
        self, mock_config, temp_project_dir
    ):
        """Test setup installs normalized package names for declared haxelibs."""
        profile_dir = temp_project_dir / "build" / "profiles"
        profile_dir.mkdir(parents=True)
        (profile_dir / "main.json").write_text(
            '{"libs": ["heaps:git", "domkit"]}',
            encoding="utf-8",
        )

        module_dir = temp_project_dir / "modules" / "testmodule"
        module_dir.mkdir()
        (module_dir / "module.json").write_text(
            '{"libs": ["heaps", "deepnightLibs"]}',
            encoding="utf-8",
        )

        assert _setup_haxe_libs(mock_config) == [
            "heaps",
            "domkit",
            "deepnightLibs",
            "utest",
            "hxnodejs",
        ]
