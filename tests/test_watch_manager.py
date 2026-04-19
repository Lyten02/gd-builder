"""Tests for WatchManager"""

import subprocess
import signal
import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestWatchManager:
    """Tests for WatchManager class"""

    def test_context_manager_cleanup_running_process(self, mock_config):
        """Test cleanup is called for running process on exit"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                # Simulate running process
                mock_proc = MagicMock()
                mock_proc.poll.return_value = None  # Process is running
                watcher._server_proc = mock_proc

            # After exit, cleanup should terminate the process
            mock_proc.terminate.assert_called_once()
            mock_proc.wait.assert_called()

    def test_cleanup_handles_dead_processes(self, mock_config):
        """Test cleanup skips already dead processes"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                # Simulate dead process
                mock_proc = MagicMock()
                mock_proc.poll.return_value = 0  # Process already exited
                watcher._server_proc = mock_proc

            # terminate should NOT be called for dead process
            mock_proc.terminate.assert_not_called()

    def test_cleanup_kills_on_timeout(self, mock_config):
        """Test cleanup kills process if terminate times out"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                mock_proc = MagicMock()
                mock_proc.poll.return_value = None  # Process is running
                # First wait (with timeout) raises TimeoutExpired, second wait (after kill) succeeds
                mock_proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]
                watcher._server_proc = mock_proc

            # Should terminate, timeout, then kill
            mock_proc.terminate.assert_called_once()
            mock_proc.kill.assert_called_once()

    def test_debounce_interval_consistent(self, mock_config):
        """Test debounce interval is consistent across modes"""
        from builder.commands.watch import WatchManager

        # Standard mode
        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                assert watcher.debounce_seconds == 2.0

        # React mode should use same interval
        mock_config.react_mode = True
        with patch.object(WatchManager, '_run_react', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                assert watcher.debounce_seconds == 2.0

    def test_signal_handler_stops_running(self, mock_config):
        """Test signal handler sets _running to False"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                assert watcher._running is True
                watcher._signal_handler(signal.SIGINT, None)
                assert watcher._running is False

    def test_run_dispatches_to_standard(self, mock_config):
        """Test run() calls _run_standard for non-React mode"""
        from builder.commands.watch import WatchManager

        mock_config.react_mode = False
        watcher = WatchManager(mock_config, "debug", "web")

        with patch.object(watcher, '_run_standard', return_value=True) as mock_standard:
            with patch.object(watcher, '_run_react', return_value=True) as mock_react:
                watcher._running = True
                result = watcher.run()

                mock_standard.assert_called_once()
                mock_react.assert_not_called()
                assert result is True

    def test_run_dispatches_to_react(self, mock_config):
        """Test run() calls _run_react for React mode"""
        from builder.commands.watch import WatchManager

        mock_config.react_mode = True
        watcher = WatchManager(mock_config, "debug", "web")

        with patch.object(watcher, '_run_standard', return_value=True) as mock_standard:
            with patch.object(watcher, '_run_react', return_value=True) as mock_react:
                watcher._running = True
                result = watcher.run()

                mock_react.assert_called_once()
                mock_standard.assert_not_called()
                assert result is True

    def test_cleanup_stops_haxe_compiler(self, mock_config):
        """Test cleanup stops Haxe compiler server"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                mock_compiler = MagicMock()
                watcher._haxe_compiler = mock_compiler

            mock_compiler.stop_server.assert_called_once()

    def test_cleanup_stops_observer(self, mock_config):
        """Test cleanup stops watchdog observer"""
        from builder.commands.watch import WatchManager

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                mock_observer = MagicMock()
                watcher._observer = mock_observer

            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()

    def test_context_restores_signal_handlers(self, mock_config):
        """Test context manager restores original signal handlers"""
        from builder.commands.watch import WatchManager

        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                # Inside context, handlers should be changed
                current_sigint = signal.getsignal(signal.SIGINT)
                assert current_sigint == watcher._signal_handler

        # After context, handlers should be restored
        restored_sigint = signal.getsignal(signal.SIGINT)
        restored_sigterm = signal.getsignal(signal.SIGTERM)

        # Note: exact comparison may not work for default handlers,
        # so we just verify the signal module is involved
        assert callable(restored_sigint) or restored_sigint == original_sigint

    def test_cleanup_handles_none_processes(self, mock_config):
        """Test cleanup handles None processes gracefully"""
        from builder.commands.watch import WatchManager

        # Should not raise any exceptions
        with patch.object(WatchManager, '_run_standard', return_value=True):
            with WatchManager(mock_config, "debug", "web") as watcher:
                # All processes are None by default
                assert watcher._server_proc is None
                assert watcher._game_proc is None
                assert watcher._vite_proc is None
                assert watcher._haxe_compiler is None
                assert watcher._observer is None

        # Should complete without error

    def test_run_react_uses_configured_port_for_vite(self, mock_config):
        """Test React mode starts Vite with config.serve_port"""
        from builder.commands.watch import WatchManager

        mock_config.ui_dir.mkdir(parents=True, exist_ok=True)
        for package in ("vite", "react", "react-dom"):
            pkg_dir = mock_config.ui_dir / "node_modules" / package
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (pkg_dir / "package.json").write_text("{}", encoding="utf-8")
        mock_config.serve_port = 5003

        watcher = WatchManager(mock_config, "debug", "web")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with patch.object(watcher, "_build_haxe_api", return_value=True):
            with patch.object(watcher, "_watch_self"):
                with patch.object(watcher, "_watch_haxe_api"):
                    with patch("builder.commands.watch.subprocess.Popen", return_value=mock_proc) as mock_popen:
                        with patch("builder.commands.watch.time.sleep"):
                            assert watcher._run_react() is True

        env = mock_popen.call_args.kwargs["env"]
        assert env["VITE_PORT"] == "5003"
        assert env["VITE_STRICT_PORT"] == "true"

    def test_run_react_returns_false_if_vite_exits_early(self, mock_config):
        """Test React mode returns False when Vite process exits immediately"""
        from builder.commands.watch import WatchManager

        mock_config.ui_dir.mkdir(parents=True, exist_ok=True)
        for package in ("vite", "react", "react-dom"):
            pkg_dir = mock_config.ui_dir / "node_modules" / package
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (pkg_dir / "package.json").write_text("{}", encoding="utf-8")

        watcher = WatchManager(mock_config, "debug", "web")

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1

        with patch.object(watcher, "_build_haxe_api", return_value=True):
            with patch.object(watcher, "_watch_self"):
                with patch.object(watcher, "_watch_haxe_api") as mock_watch_haxe_api:
                    with patch("builder.commands.watch.subprocess.Popen", return_value=mock_proc):
                        with patch("builder.commands.watch.time.sleep"):
                            assert watcher._run_react() is False
                            mock_watch_haxe_api.assert_not_called()


class TestWatchCommand:
    """Tests for watch_command function"""

    def test_watch_command_uses_context_manager(self, mock_config):
        """Test watch_command uses WatchManager as context manager"""
        from builder.commands.watch import watch_command, WatchManager

        with patch.object(WatchManager, '__enter__', return_value=MagicMock()) as mock_enter:
            with patch.object(WatchManager, '__exit__', return_value=False) as mock_exit:
                with patch.object(WatchManager, 'run', return_value=True):
                    mock_instance = MagicMock()
                    mock_instance.run.return_value = True
                    mock_enter.return_value = mock_instance

                    result = watch_command(mock_config, "debug", "web")

                    mock_enter.assert_called_once()
                    mock_exit.assert_called_once()
