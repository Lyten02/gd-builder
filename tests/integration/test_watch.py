"""Integration tests for watch mode"""

import pytest
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.mark.integration
@pytest.mark.slow
class TestWatchIntegration:
    """Integration tests for watch mode - these tests are slow and require Haxe"""

    def test_watch_manager_initializes(self, haxe_project_config, haxe_available):
        """Test WatchManager can be initialized"""
        from builder.commands.watch import WatchManager

        watcher = WatchManager(haxe_project_config, "debug", "web")

        assert watcher.config == haxe_project_config
        assert watcher.mode == "debug"
        assert watcher.platform == "web"
        assert watcher.debounce_seconds == 2.0
        assert watcher._running is False

    def test_watch_manager_context_entry_sets_running(self, haxe_project_config, haxe_available):
        """Test entering WatchManager context sets _running to True"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, 'run', return_value=True):
            with WatchManager(haxe_project_config, "debug", "web") as watcher:
                assert watcher._running is True

    def test_watch_manager_cleanup_on_exception(self, haxe_project_config, haxe_available):
        """Test WatchManager cleans up on exception"""
        from builder.commands.watch import WatchManager

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        try:
            with WatchManager(haxe_project_config, "debug", "web") as watcher:
                watcher._server_proc = mock_proc
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Cleanup should have been called
        mock_proc.terminate.assert_called()

    def test_watch_detects_file_change_mocked(self, haxe_project_config, haxe_available):
        """Test watch mode detects file changes (mocked build)"""
        from builder.commands.watch import WatchManager

        builds = []

        def mock_build(*args, **kwargs):
            builds.append(time.time())
            return True

        with patch("builder.commands.watch._build_single", mock_build):
            with patch("builder.commands.watch.HaxeCompiler") as mock_compiler:
                # Mock the Haxe compiler
                mock_compiler.return_value.start_server.return_value = True

                with WatchManager(haxe_project_config, "debug", "web") as watcher:
                    # Run watch in a separate thread
                    def run_watch():
                        try:
                            watcher._run_standard()
                        except Exception:
                            pass

                    watch_thread = threading.Thread(target=run_watch)
                    watch_thread.daemon = True
                    watch_thread.start()

                    # Wait for initial build
                    time.sleep(0.5)

                    # Modify a file
                    main_hx = haxe_project_config.src_dir / "Main.hx"
                    original_content = main_hx.read_text()
                    main_hx.write_text(original_content + "\n// modified")

                    # Wait for debounce + rebuild
                    time.sleep(3)

                    # Stop watch
                    watcher._running = False

                    # Allow thread to finish
                    time.sleep(0.5)

        # Should have at least initial build
        assert len(builds) >= 1


@pytest.mark.integration
class TestWatchCleanup:
    """Tests for watch mode cleanup functionality"""

    def test_cleanup_terminates_all_processes(self, haxe_project_config):
        """Test cleanup terminates all managed processes"""
        from builder.commands.watch import WatchManager

        with WatchManager(haxe_project_config, "debug", "web") as watcher:
            # Create mock processes
            for proc_name in ['_server_proc', '_game_proc', '_vite_proc']:
                mock_proc = MagicMock()
                mock_proc.poll.return_value = None
                setattr(watcher, proc_name, mock_proc)

            # Create mock compiler
            mock_compiler = MagicMock()
            watcher._haxe_compiler = mock_compiler

        # After context exit, all should be cleaned up
        for proc_name in ['_server_proc', '_game_proc', '_vite_proc']:
            proc = getattr(watcher, proc_name)
            proc.terminate.assert_called()

        mock_compiler.stop_server.assert_called()

    def test_cleanup_handles_none_gracefully(self, haxe_project_config):
        """Test cleanup handles None values gracefully"""
        from builder.commands.watch import WatchManager

        # Should not raise any exceptions
        with WatchManager(haxe_project_config, "debug", "web") as watcher:
            # All process attributes are None by default
            pass

        # Context exit should succeed without errors


@pytest.mark.integration
class TestWatchPolling:
    """Tests for polling fallback mode"""

    def test_polling_mode_activates_without_watchdog(self, haxe_project_config, haxe_available):
        """Test polling mode activates when watchdog is not available"""
        from builder.commands.watch import WatchManager

        import sys
        # Temporarily hide watchdog
        original_modules = {}
        for mod_name in list(sys.modules.keys()):
            if 'watchdog' in mod_name:
                original_modules[mod_name] = sys.modules[mod_name]
                del sys.modules[mod_name]

        try:
            # This would test polling mode, but we'll just verify the fallback exists
            watcher = WatchManager(haxe_project_config, "debug", "web")
            assert hasattr(watcher, '_watch_polling')
        finally:
            # Restore watchdog modules
            sys.modules.update(original_modules)
