"""Watch command implementation with WatchManager (self-reload v5 - PollingObserver)"""
# TEST: This comment triggers self-reload test

import os
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional

from ..config import ProjectConfig
from ..commands.build import _build_single
from ..platforms.web import WebPlatform
from ..platforms.cpp import CppPlatform
from ..services.haxe import build_platform, HaxeCompiler
from ..utils.logger import log_step, log_success, log_warn, log_info, log_error
from ..utils.path import path_for_project


def _port_in_use(port: int) -> bool:
    """True if someone is already listening on localhost:<port>."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def _kill_listener(port: int) -> list[int]:
    """Kill the Windows process listening on localhost:<port>.

    Returns the killed PIDs. Skips our own PID so we don't commit suicide
    if called from a child that happens to share the port.
    """
    killed: list[int] = []
    if sys.platform != "win32":
        return killed
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return killed
    token = f":{port}"
    pids: set[int] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        # Columns: Proto Local Foreign State PID
        if len(parts) >= 5 and parts[0] == "TCP" and parts[1].endswith(token) and parts[3] == "LISTENING":
            try:
                pids.add(int(parts[4]))
            except ValueError:
                continue
    my_pid = os.getpid()
    for pid in pids:
        if pid == my_pid:
            continue
        r = subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            killed.append(pid)
    return killed


def _cleanup_stale_processes(serve_port: int, haxe_port: int) -> None:
    """Kill stale dev-loop processes before starting a fresh watch.

    - `haxe.exe` keeps a macro cache in memory — a left-over compile server
      serves stale `hxd.Res.initEmbed()` output, so res/*.json edits don't
      make it into game.js. Always nuke any running haxe.exe so watch owns
      the server it later relies on.
    - Anything listening on serve_port / haxe_port is either our previous
      dev HTTP server or a second watch — kill it so this watch binds cleanly.

    Windows only. On other platforms it's a no-op (users can Ctrl-C cleanly).
    """
    if sys.platform != "win32":
        return
    subprocess.run(
        ["taskkill", "/F", "/IM", "haxe.exe"],
        capture_output=True, text=True, timeout=5,
    )
    serve_killed = _kill_listener(serve_port)
    haxe_killed = _kill_listener(haxe_port)
    if serve_killed or haxe_killed:
        killed = serve_killed + haxe_killed
        log_info(f"Cleaned up stale processes: {killed}")


class WatchManager:
    """Context manager for watch mode with guaranteed cleanup"""

    def __init__(self, config: ProjectConfig, mode: str, platform: str):
        self.config = config
        self.mode = mode
        self.platform = platform
        self.debounce_seconds = 2.0  # retained for polling fallback only

        # Encapsulated process state
        self._server_proc: Optional[subprocess.Popen] = None
        self._game_proc: Optional[subprocess.Popen] = None
        self._vite_proc: Optional[subprocess.Popen] = None
        self._backend_procs: list[subprocess.Popen] = []  # Backend servers
        self._haxe_compiler: Optional[HaxeCompiler] = None
        self._observer = None  # watchdog Observer
        self._scripts_observer = None  # For self-reload
        self._running = False
        self._original_sigint = None
        self._original_sigterm = None

        # Supersede-model build worker state:
        #   Events set _pending=True (coalescing the burst). A single worker
        #   thread consumes the flag, runs the build, and — if more events
        #   arrived while building — discards the result and rebuilds. This
        #   guarantees at most ONE reload per burst of changes (no flicker).
        self._build_cv = threading.Condition()
        self._pending = False
        self._pending_path: Optional[Path] = None
        self._build_worker: Optional[Thread] = None
        self._build_fn = None  # set per mode: _build_single or _build_haxe_api
        # Per-path event cooldown. An atomic save (write → delete → rename)
        # often surfaces as multiple FS events over a short window. We keep
        # the cooldown tight (~0.3s) so real back-to-back manual saves (≥0.5s
        # apart) aren't dropped — but the cascade of stragglers from a single
        # save collapses into one trigger. Supersede handles longer bursts.
        self._event_cooldown_sec = 0.3
        self._last_trigger_time: dict[str, float] = {}
        # Коалесценция: перед стартом билда ждём _quiet_window_sec тишины.
        # Каждое новое событие сбрасывает отсчёт — бёрст сохранений
        # схлопывается в один билд ДО компиляции, без двойного "Building...".
        self._quiet_window_sec = 0.4
        self._last_signal_time = 0.0
        # Жёсткая гарантия: в _build_fn() в любой момент времени не более
        # одного потока, даже если появится второй воркер.
        self._build_lock = threading.Lock()
        # Paths we touched ourselves (e.g. AppBase.hx to bust macro cache).
        # value = wall-clock time until which observer events on this path
        # should be suppressed, so our own touch doesn't trigger a rebuild
        # loop.
        self._self_touch_suppress_until: dict[str, float] = {}

    def __enter__(self):
        self._running = True
        # Save original handlers
        self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        # Restore original handlers
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        return False  # Don't suppress exceptions

    def cleanup(self) -> None:
        """Guaranteed cleanup of all processes"""
        self._running = False
        print("\n")
        log_info("Shutting down...")

        # Terminate all processes with timeout
        all_procs = [self._vite_proc, self._game_proc, self._server_proc] + self._backend_procs
        for proc in all_procs:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        # Stop Haxe compiler server
        if self._haxe_compiler:
            self._haxe_compiler.stop_server()

        # Stop file observer
        if self._observer:
            self._observer.stop()
            try:
                self._observer.join(timeout=2)
            except Exception:
                pass

        # Stop scripts observer
        if self._scripts_observer:
            self._scripts_observer.stop()
            try:
                self._scripts_observer.join(timeout=2)
            except Exception:
                pass

    def _signal_handler(self, signum, frame):
        """Handle SIGINT/SIGTERM"""
        self._running = False

    def _watch_self(self) -> None:
        """Watch build scripts for self-reload (PollingObserver for Claude Code compatibility)"""
        try:
            from watchdog.observers.polling import PollingObserver
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return

        manager = self

        class ScriptsHandler(FileSystemEventHandler):
            def on_any_event(self, event):
                if event.is_directory:
                    return
                # Только modified, created, moved (не deleted)
                if event.event_type not in ('modified', 'created', 'moved'):
                    return
                path = Path(event.src_path)
                if path.suffix != ".py":
                    return
                # Игнорируем временные файлы
                if path.name.startswith('.') or '~' in path.name:
                    return

                log_warn(f"Build script changed: {path.name}")
                log_info("Restarting watch mode...")
                manager._restart_self()

        # Find builder directory: gd-builder module or legacy starter/scripts
        builder_dir = self.config.modules_dir / "gd-builder" / "builder"
        if not builder_dir.exists() and self.config.starter_dir:
            builder_dir = self.config.starter_dir / "scripts" / "builder"

        if builder_dir.exists():
            self._scripts_observer = PollingObserver(timeout=1)
            handler = ScriptsHandler()
            self._scripts_observer.schedule(handler, str(builder_dir), recursive=True)
            self._scripts_observer.start()
            log_info(f"Watching build scripts: {builder_dir}")

    def _restart_self(self) -> None:
        """Restart the watch process"""
        import os

        # Cleanup all processes first
        self.cleanup()

        # Restart with same arguments
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def run(self) -> bool:
        """Main watch loop"""
        if self.config.react_mode:
            return self._run_react()
        return self._run_standard()

    def _get_watch_paths(self) -> list[Path]:
        """Return top-level project paths for watch mode."""
        watch_paths: list[Path] = []
        roots = [self.config.res_dir, self.config.src_dir, self.config.modules_dir]

        for path in roots:
            if path.exists():
                watch_paths.append(path)
        return watch_paths

    def _is_resource_path(self, path: Path) -> bool:
        """True when path lives under res_dir — used to decide whether to
        kick the Haxe server's macro cache before a rebuild."""
        try:
            path.relative_to(self.config.res_dir)
            return True
        except ValueError:
            return False

    def _embed_host_file(self) -> Optional[Path]:
        """Path to the .hx file that calls hxd.Res.initEmbed(), or None.

        Invalidating this file on the compile server is enough to force the
        embed macro to re-run (fast path — keeps AST cache for everything
        else). Result is cached per WatchManager instance.
        """
        if getattr(self, "_embed_host_cached", None) is not None:
            return self._embed_host_cached
        cached: Optional[Path] = None
        # Scan src/ and modules/ for the call site. First hit wins.
        for root in (self.config.src_dir, self.config.modules_dir):
            if not root.exists():
                continue
            for hx in root.rglob("*.hx"):
                try:
                    if "hxd.Res.initEmbed" in hx.read_text(encoding="utf-8", errors="ignore"):
                        cached = hx
                        break
                except OSError:
                    continue
            if cached is not None:
                break
        self._embed_host_cached = cached
        return cached

    def _is_rebuild_trigger(self, path: Path) -> bool:
        """Return True when file change should trigger a rebuild."""
        if any(x in str(path) for x in [".git", ".DS_Store", "version.json", ".buildtime", ".tmp", ".hxml"]):
            return False

        # Rebuild on source changes.
        if path.suffix == ".hx":
            return True

        # Rebuild on any resource change.
        try:
            path.relative_to(self.config.res_dir)
            return True
        except ValueError:
            return False

    def _trigger_rebuild(self, path: Path) -> None:
        """Signal the worker thread that a rebuild is needed.

        Per-path cooldown: events for the same path within
        `_event_cooldown_sec` seconds of the last trigger are ignored. This
        absorbs atomic-save stragglers (Windows rename chain often surfaces
        the same save as 2-4 events spread over ~1s via PollingObserver).
        Real back-to-back edits (user saves twice, >1s apart) still go
        through — supersede handles in-flight builds.
        """
        now = time.time()
        key = str(path)
        # Suppress self-touches (we bumped this file's mtime to bust Haxe's
        # macro cache; the observer event that follows is our own doing).
        suppress_until = self._self_touch_suppress_until.get(key, 0.0)
        if now < suppress_until:
            return
        last = self._last_trigger_time.get(key, 0.0)
        if now - last < self._event_cooldown_sec:
            return  # straggler from the previous save — ignore
        self._last_trigger_time[key] = now
        with self._build_cv:
            self._pending = True
            self._pending_path = path
            self._last_signal_time = now
            self._build_cv.notify_all()

    def _run_build_worker(self) -> None:
        """Consume pending events and run builds sequentially, superseding stale results.

        Flow:
          1. Wait for _pending.
          2. Clear it, capture triggering path, run the build.
          3. If _pending became True during the build → discard, loop (rebuild).
          4. Otherwise → deploy via _on_build_success().

        Result: bursts of file changes → single rebuild + reload at the end.
        """
        while self._running:
            with self._build_cv:
                while not self._pending and self._running:
                    self._build_cv.wait(timeout=0.5)
                if not self._running:
                    return
                # Quiet-window: ждём, пока не пройдёт _quiet_window_sec без
                # новых сигналов. Каждое _trigger_rebuild обновляет
                # _last_signal_time и будит wait() через notify_all(),
                # поэтому бёрст сохранений коалесцируется ДО старта билда.
                while self._running:
                    elapsed = time.time() - self._last_signal_time
                    remaining = self._quiet_window_sec - elapsed
                    if remaining <= 0:
                        break
                    self._build_cv.wait(timeout=remaining)
                if not self._running:
                    return
                self._pending = False
                triggering_path = self._pending_path
                self._pending_path = None

            if triggering_path is not None:
                rel = path_for_project(triggering_path, self.config.project_dir)
                now = datetime.now()
                ts = f"{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}"
                print(f"\n\033[90m{ts}\033[0m \033[33mDetected change: {rel}\033[0m")
            log_step("Recompiling...")

            # If a res/ file changed, force Haxe to re-expand
            # hxd.Res.initEmbed() so new .json/.png end up embedded in
            # game.js. Fast path: touch the macro host file — compile
            # server sees newer mtime, re-parses only that module, macro
            # re-expands, everything else stays cached (~1-2s rebuild).
            # Suppress our own filesystem event for ~3s so the touch
            # doesn't trigger another rebuild. Fall back to full server
            # restart (~6-7s cold) if the host file is missing.
            if (triggering_path is not None
                    and self._haxe_compiler is not None
                    and self._is_resource_path(triggering_path)):
                host = self._embed_host_file()
                if host is not None:
                    self._self_touch_suppress_until[str(host)] = time.time() + 3.0
                    if self._haxe_compiler.invalidate_file(host):
                        log_info(f"Touched {host.name} to re-expand embed macro")
                    else:
                        self._haxe_compiler.restart_server()
                else:
                    self._haxe_compiler.restart_server()

            try:
                with self._build_lock:
                    ok = bool(self._build_fn()) if self._build_fn else False
            except Exception as exc:
                log_error(f"Build failed with exception: {exc}")
                ok = False

            # Check if a new event arrived during the build — if so, discard.
            with self._build_cv:
                superseded = self._pending

            if superseded:
                log_info("New changes arrived during build — superseding")
                continue

            if ok:
                self._on_build_success()
            else:
                print("\a", end="", flush=True)

    def _start_build_worker(self, build_fn) -> None:
        """Kick off the supersede worker with the given build callable.

        Guard against double-start: if a worker is already alive, refuse.
        This makes triple-parallel builds impossible by construction even if
        the caller path has a bug.
        """
        if self._build_worker is not None and self._build_worker.is_alive():
            log_warn(f"Build worker already running (PID {os.getpid()}) — refusing to start another")
            return
        self._build_fn = build_fn
        self._build_worker = Thread(target=self._run_build_worker, daemon=True, name="build-worker")
        self._build_worker.start()

    def _iter_polled_files(self):
        """Iterate files used by polling fallback."""
        for root in self._get_watch_paths():
            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue
                if self._is_rebuild_trigger(file_path):
                    yield file_path

    def _run_standard(self) -> bool:
        """Standard Heaps watch mode"""
        log_info(f"Turbo Watch Mode Activated (pid={os.getpid()})")

        # Reclaim ports and kill any orphan haxe.exe from a prior run, so
        # this watch owns its compile server (needed for restart_server to
        # refresh the hxd.Res.initEmbed macro cache on res/ changes).
        _cleanup_stale_processes(self.config.serve_port, self.config.haxe_server_port)

        # Start Haxe compilation server
        self._haxe_compiler = HaxeCompiler(self.config)
        self._haxe_compiler.start_server(self.config.haxe_server_port)

        # Initial build
        initial_ok = _build_single(self.config, self.mode, self.platform)
        if not initial_ok:
            log_warn("Initial build failed. Waiting for changes...")

        # Start web server for web platform
        if self.platform == "web":
            web_dir = self.config.get_web_dir(self.mode)
            web_dir.mkdir(parents=True, exist_ok=True)

            # Create index.html
            plat = WebPlatform(self.config, self.mode)
            index_path = web_dir / "index.html"
            if not index_path.exists():
                plat._create_index_html(index_path)

            # Start Python HTTP server. Custom no-cache server: forces
            # `Cache-Control: no-store` so `location.reload()` always fetches
            # fresh res/* files (default stdlib http.server sets long max-age
            # and makes hxd.Res.load see stale data after a rebuild).
            dev_server = Path(__file__).resolve().parent.parent / "dev_server.py"
            self._server_proc = subprocess.Popen(
                ["python3", str(dev_server), str(self.config.serve_port)],
                cwd=web_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log_success(f"Server running: http://localhost:{self.config.serve_port}")

        # Watch build scripts for self-reload
        self._watch_self()

        # Watch for changes
        self._watch_files()
        return True

    def _run_react(self) -> bool:
        """React watch mode with Vite"""
        log_info(f"React Watch Mode (pid={os.getpid()})")

        # Same rationale as _run_standard: claim our ports and the haxe server.
        _cleanup_stale_processes(self.config.serve_port, self.config.haxe_server_port)

        # Start Haxe compilation server
        self._haxe_compiler = HaxeCompiler(self.config)
        self._haxe_compiler.start_server(self.config.haxe_server_port)

        # Build Haxe API
        if not self._build_haxe_api():
            log_warn("Initial Haxe API build failed. Continuing...")

        # Start backend servers if configured
        if self.config.servers:
            self._start_backend_servers()

        # Start Vite
        ui_dir = self.config.ui_dir
        if not ui_dir.exists():
            log_error(f"React UI directory not found: {ui_dir}")
            return False

        # Install dependencies if needed. A stale/partial node_modules directory
        # (e.g. only Vite cache) is not enough for `npm run dev`.
        if self._missing_react_dependencies(ui_dir):
            log_step("Installing React dependencies...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=ui_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                log_error(f"npm install failed:\n{result.stderr}")
                return False

        log_step("Starting Vite dev server...")
        import os
        env = dict(os.environ)
        env["BUILD_MODE"] = self.mode
        # Always honor watch config and CLI flags instead of inherited shell env.
        env["VITE_HOST"] = "0.0.0.0"
        env["VITE_PORT"] = str(self.config.serve_port)
        env["VITE_STRICT_PORT"] = "true"
        if self.config.gamepush_enabled:
            env["GAMEPUSH_ENABLED"] = "true"
            if self.config.gp_project_id:
                env["GP_PROJECT_ID"] = self.config.gp_project_id
            if self.config.gp_public_token:
                env["GP_PUBLIC_TOKEN"] = self.config.gp_public_token

        self._vite_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=ui_dir,
            env=env,
        )
        time.sleep(2)
        exit_code = self._vite_proc.poll()
        if exit_code is not None:
            log_error(
                f"Vite failed to start (exit code {exit_code}). "
                f"Requested URL: http://localhost:{env['VITE_PORT']}"
            )
            return False
        log_success(f"Vite running: http://localhost:{env['VITE_PORT']} (host={env['VITE_HOST']})")

        # Watch build scripts for self-reload
        self._watch_self()

        # Watch Haxe files
        self._watch_haxe_api()
        return True

    def _missing_react_dependencies(self, ui_dir: Path) -> bool:
        """Return True when required UI packages are not installed."""
        required = (
            ui_dir / "node_modules" / "vite" / "package.json",
            ui_dir / "node_modules" / "react" / "package.json",
            ui_dir / "node_modules" / "react-dom" / "package.json",
        )
        return not all(path.exists() for path in required)

    def _build_haxe_api(self) -> bool:
        """Build Haxe API for React"""
        start_time = time.time()
        log_step(f"Building Haxe API for React ({self.mode})...")

        # Create watch directory
        watch_dir = self.config.ui_dir / "public" / "watch"
        watch_dir.mkdir(parents=True, exist_ok=True)

        # Build API
        api_hxml = self.config.build_dir / "api_main.hxml"
        api_hxml.parent.mkdir(parents=True, exist_ok=True)

        starter_src = self.config.project_dir / "modules" / "haxeheaps-starter" / "src"
        if self.config.starter_dir and (self.config.starter_dir / "src").exists():
            starter_src = self.config.starter_dir / "src"

        api_content = f"""# Haxe API build for React integration
-cp src
-cp {path_for_project(starter_src, self.config.project_dir)}
-main bridge.Api
-js ui/public/watch/quickpaint.js
-D js-es=6
-dce full
-debug
"""
        api_hxml.write_text(api_content)

        from ..utils.process import run_command
        result = run_command(["haxe", str(api_hxml)], cwd=self.config.project_dir)

        if not result.success:
            log_error(f"Haxe API build failed: {result.stderr}")
            return False

        duration_ms = int((time.time() - start_time) * 1000)
        log_success(f"Haxe API built: ui/public/watch/quickpaint.js ({duration_ms}ms)")

        if _build_single(self.config, self.mode, "web"):
            web_dir = self.config.get_web_dir(self.mode)
            game_js = web_dir / "game.js"
            if game_js.exists():
                import shutil
                shutil.copy(game_js, watch_dir / "game.js")
                game_map = web_dir / "game.js.map"
                if game_map.exists():
                    shutil.copy(game_map, watch_dir / "game.js.map")
                log_success("Runtime built: ui/public/watch/game.js")
        else:
            return False

        return True

    def _start_backend_servers(self) -> None:
        """Start all configured backend servers"""
        for server_dir in self.config.servers:
            self._start_single_backend(server_dir)

    def _start_single_backend(self, server_dir: Path) -> None:
        """Start a single backend server"""
        import os

        server_name = server_dir.name

        # Check if package.json exists
        if not (server_dir / "package.json").exists():
            log_error(f"No package.json found in {server_dir}")
            return

        # Always ensure dependencies are up-to-date
        # npm install is smart enough to skip if nothing changed (~1-2s)
        log_step(f"Checking {server_name} dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=server_dir,
            capture_output=True,  # Hide npm output unless error
            text=True
        )
        if result.returncode != 0:
            log_error(f"Failed to install {server_name} dependencies:")
            print(result.stderr)
            return

        # Start dev server
        log_step(f"Starting {server_name} backend...")
        env = dict(os.environ)
        env["NODE_ENV"] = "development"

        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=server_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._backend_procs.append(proc)
        time.sleep(2)  # Give server time to start

        # Check if process is still running
        if proc.poll() is not None:
            # Process already exited
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            log_error(f"Backend {server_name} failed to start:\n{stderr}")
        else:
            log_success(f"Backend {server_name} started (PID: {proc.pid})")

    def _watch_files(self) -> None:
        """Watch files for changes using watchdog (PollingObserver for Claude Code compatibility)"""
        try:
            from watchdog.observers.polling import PollingObserver
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            log_warn("watchdog not installed. Using polling mode.")
            self._watch_polling()
            return

        manager = self  # Reference for closure

        class HaxeHandler(FileSystemEventHandler):
            def on_any_event(self, event):
                if not manager._running:
                    return
                if event.is_directory:
                    return
                # Claude Code uses atomic write (write-and-rename) which
                # generates moved/created events.
                if event.event_type not in ('modified', 'created', 'moved'):
                    return
                path = Path(event.src_path)
                # Ignore temp files from atomic writes.
                if path.name.startswith('.') or '~' in path.name:
                    return
                if not manager._is_rebuild_trigger(path):
                    return
                # Supersede model: signal the worker. Bursts of events coalesce
                # into a single rebuild + reload.
                manager._trigger_rebuild(path)

        # Start the supersede build worker for standard platform builds.
        self._start_build_worker(
            lambda: _build_single(self.config, self.mode, self.platform)
        )

        self._observer = PollingObserver(timeout=1)
        handler = HaxeHandler()

        for path in self._get_watch_paths():
            if path.exists():
                self._observer.schedule(handler, str(path), recursive=True)
                log_info(f"Watching: {path}")

        self._observer.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        self._observer.stop()
        self._observer.join()

        # Wake worker so it can exit cleanly.
        with self._build_cv:
            self._build_cv.notify_all()

    def _watch_haxe_api(self) -> None:
        """Watch Haxe files for React mode (PollingObserver for Claude Code compatibility)"""
        try:
            from watchdog.observers.polling import PollingObserver
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            log_warn("watchdog not installed. Haxe changes won't auto-rebuild.")
            # Keep running for Vite
            while self._running:
                time.sleep(1)
            return

        manager = self  # Reference for closure

        class HaxeHandler(FileSystemEventHandler):
            def on_any_event(self, event):
                if not manager._running:
                    return
                if event.is_directory:
                    return
                if event.event_type not in ('modified', 'created', 'moved'):
                    return
                path = Path(event.src_path)
                if path.name.startswith('.') or '~' in path.name:
                    return
                if not manager._is_rebuild_trigger(path):
                    return
                manager._trigger_rebuild(path)

        # Start supersede build worker targeting the Haxe-API build.
        self._start_build_worker(self._build_haxe_api)

        self._observer = PollingObserver(timeout=1)
        handler = HaxeHandler()

        for path in self._get_watch_paths():
            if path.exists():
                self._observer.schedule(handler, str(path), recursive=True)
                log_info(f"Watching: {path}")

        self._observer.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        self._observer.stop()
        self._observer.join()

        with self._build_cv:
            self._build_cv.notify_all()

    def _watch_polling(self) -> None:
        """Fallback polling mode"""
        import hashlib

        last_hash = ""

        while self._running:
            # Calculate hash of all files that should trigger rebuild
            current_hash = ""
            for watched_file in self._iter_polled_files():
                try:
                    current_hash += f"{watched_file}:{watched_file.stat().st_mtime_ns};"
                except FileNotFoundError:
                    continue

            current_hash = hashlib.md5(current_hash.encode()).hexdigest()

            if current_hash != last_hash and last_hash:
                log_step("Change detected, recompiling...")
                if _build_single(self.config, self.mode, self.platform):
                    self._on_build_success()

            last_hash = current_hash
            time.sleep(self.debounce_seconds)

    def _on_build_success(self) -> None:
        """Handle successful build"""
        if self.platform == "web":
            web_dir = self.config.get_web_dir(self.mode)
            # Update version.json for auto-reload
            plat = WebPlatform(self.config, self.mode)
            plat._generate_version_json()

            # Deploy to Netlify if enabled
            if self.config.netlify_deploy:
                from ..services.netlify import deploy_netlify_watch
                deploy_netlify_watch(self.config)

        elif self.platform == "cpp":
            # Restart game
            if self._game_proc and self._game_proc.poll() is None:
                self._game_proc.terminate()
                self._game_proc.wait()

            binary = self.config.bin_dir / "game"
            if binary.exists():
                self._game_proc = subprocess.Popen([str(binary)], cwd=self.config.project_dir)


def watch_command(config: ProjectConfig, mode: str, platform: str) -> bool:
    """Watch for changes and rebuild"""
    with WatchManager(config, mode, platform) as watcher:
        return watcher.run()
