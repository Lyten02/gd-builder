"""Haxe compiler wrapper and .hxml generation"""

import socket
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ..config import ProjectConfig
from ..utils.logger import log_step, log_success, log_error, log_info, log_warn
from ..utils.path import path_for_project
from ..utils.process import run_command, ProcessResult


def _server_listening(port: int, timeout: float = 0.1) -> bool:
    """Probe whether a Haxe compile server is listening on localhost:<port>.

    Used to auto-reuse a long-running server started by watch mode, so every
    rebuild reconnects via `--connect <port>` (AST cache hit, ~1-2s) instead
    of paying the cold-compile cost (~7s)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False


@dataclass
class HaxeCompileResult:
    """Result of Haxe compilation"""
    success: bool
    duration_ms: int
    output_path: Optional[Path] = None
    error_message: str = ""


class HaxeCompiler:
    """Haxe compiler wrapper"""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self._server_port: Optional[int] = None
        # Tracked only when WE started the server. If the port was already
        # bound by an earlier process, this stays None and restart_server()
        # is a no-op (we can't kill something we don't own).
        self._server_proc = None

    def generate_hxml(self, platform: str, mode: str) -> Path:
        """Generate .hxml build configuration"""
        output_file = self.config.get_hxml_path(platform, mode)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Auto-generated build file",
            f"# Platform: {platform}",
            f"# Mode: {mode}",
            f"# Project: {self.config.project_dir}",
            "",
        ]

        # Source paths
        for src_path in self.config.get_source_paths():
            lines.append(f"-cp {path_for_project(src_path, self.config.project_dir)}")

        lines.extend([
            f"-main {self.config.get_main_class()}",
            "-lib heaps",
        ])

        # Platform-specific settings
        if platform == "web":
            web_dir = self.config.get_web_dir(mode)
            web_dir.mkdir(parents=True, exist_ok=True)
            rel_web = path_for_project(web_dir, self.config.project_dir)

            lines.extend([
                f"-js {rel_web}/game.js",
                "-D canvas_id=webgl",
                "-D windowSize=800x600",
            ])

            # Check for LDtk levels
            ldtk_file = self.config.res_dir / "levels" / "game.ldtk"
            if ldtk_file.exists():
                lines.append(f"--resource {ldtk_file}@levels")

            if mode == "debug":
                lines.extend([
                    "-D source_maps",
                    "-debug",
                ])
            else:
                lines.extend([
                    "-dce full",
                    "-D no-traces",
                    "-D no_debug",
                ])

        elif platform == "cpp":
            lines.extend([
                "-lib heaps",
                "-lib hlsdl",
                "-lib hlopenal",
                "-lib ldtk-haxe-api",
                "-D resourcesPath=res",
                "-hl bin/hlc/game.c",
            ])
            if mode == "debug":
                lines.append("-debug")

        # GamePush
        if self.config.gamepush_enabled and platform == "web":
            lines.append("-D gamepush")

        # Resources path
        if self.config.res_dir.exists():
            lines.append(f"-D resourcesPath={path_for_project(self.config.res_dir, self.config.project_dir)}")

        output_file.write_text("\n".join(lines))
        return output_file

    def compile(self, hxml_path: Path, use_server: bool = False) -> HaxeCompileResult:
        """Compile using .hxml file.

        Auto-reuses a running compile server: if watch mode has started
        `haxe --wait <port>` in the background, every rebuild issues
        `haxe --connect <port> <hxml>` and hits the AST cache (~1-2s vs
        ~7s cold). No-op when no server is listening.
        """
        start_time = time.time()

        connect_port: Optional[int] = None
        if use_server and self._server_port:
            connect_port = self._server_port
        elif _server_listening(self.config.haxe_server_port):
            connect_port = self.config.haxe_server_port

        cmd = ["haxe"]
        if connect_port is not None:
            cmd.extend(["--connect", str(connect_port)])
        cmd.append(str(hxml_path))

        result = run_command(cmd, cwd=self.config.project_dir)
        duration_ms = int((time.time() - start_time) * 1000)

        if result.success:
            return HaxeCompileResult(
                success=True,
                duration_ms=duration_ms,
                output_path=hxml_path,
            )
        else:
            return HaxeCompileResult(
                success=False,
                duration_ms=duration_ms,
                error_message=result.stderr or result.stdout,
            )

    def compile_no_output(self, hxml_path: Path) -> HaxeCompileResult:
        """Compile without generating output (syntax check)"""
        cmd = ["haxe", str(hxml_path), "--no-output"]
        result = run_command(cmd, cwd=self.config.project_dir)

        return HaxeCompileResult(
            success=result.success,
            duration_ms=result.duration_ms,
            error_message=result.stderr or result.stdout if not result.success else "",
        )

    def start_server(self, port: int = 6000) -> bool:
        """Start Haxe compilation server"""
        # Check if port is already in use
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("localhost", port))
            sock.close()
        except socket.error:
            # Port in use, server might already be running
            self._server_port = port
            return True

        # Start server
        import subprocess
        try:
            self._server_proc = subprocess.Popen(
                ["haxe", "--wait", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            self._server_port = port
            log_success(f"Haxe server started on port {port}")
            return True
        except Exception as e:
            log_error(f"Failed to start Haxe server: {e}")
            return False

    def stop_server(self) -> None:
        """Stop Haxe compilation server (only if we started it)."""
        import subprocess
        if self._server_proc is not None and self._server_proc.poll() is None:
            self._server_proc.terminate()
            try:
                self._server_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
                self._server_proc.wait()
        self._server_proc = None
        self._server_port = None

    def restart_server(self) -> bool:
        """Restart the compile server to drop the macro cache.

        Needed when `res/` files change: Haxe caches the result of
        `hxd.Res.initEmbed()` in-memory on the server, so new .json/.png
        files are not picked up until the server is restarted.
        """
        if self._server_proc is None:
            # We don't own the server (someone else started it on this port).
            # Safest: fall through — next compile will hit the stale cache,
            # user needs to kill that process manually once.
            log_warn("Haxe server not owned by this watch — can't restart (kill external haxe.exe if res/ changes are stuck)")
            return False
        port = self._server_port or 6000
        log_info(f"Restarting Haxe server on port {port} to refresh res/ embed cache")
        self.stop_server()
        return self.start_server(port)

    def invalidate_file(self, hx_path: Path) -> bool:
        """Bump the module's mtime so the compile server re-parses it.

        Haxe 4.3's CLI does not expose `--server-invalidate` (that's a
        socket-protocol command only). But the server does check file
        mtimes on each compile: if a module is newer than its cached AST,
        it's re-parsed, and all macros inside are re-expanded. Touching
        the host of `hxd.Res.initEmbed()` therefore forces the embed
        macro to re-scan res/, while every other module stays cached —
        next compile is incremental (~1-2s) instead of cold (~6-7s).

        The caller is responsible for suppressing the file-watcher event
        that results from this touch (otherwise we'd loop-rebuild).
        """
        if not hx_path.exists():
            return False
        try:
            hx_path.touch()
            return True
        except OSError:
            return False


def build_platform(config: ProjectConfig, platform: str, mode: str) -> HaxeCompileResult:
    """Build a platform with logging"""
    log_step(f"Building {platform} ({mode})...")

    compiler = HaxeCompiler(config)

    # Generate hxml
    hxml_path = compiler.generate_hxml(platform, mode)

    if config.verbose:
        log_info(f"Using build file: {hxml_path}")
        print(hxml_path.read_text())

    # Compile
    result = compiler.compile(hxml_path)

    if result.success:
        log_success(f"Built {platform} ({mode}) in {result.duration_ms}ms")
    else:
        log_error(f"Build failed: {result.error_message}")
        # Bell sound on error
        print("\a", end="", flush=True)

    return result


def build_test(config: ProjectConfig) -> HaxeCompileResult:
    """Build tests"""
    log_step("Compiling tests...")

    test_hxml = config.build_dir / "test.hxml"
    if not test_hxml.exists():
        return HaxeCompileResult(
            success=False,
            duration_ms=0,
            error_message=f"test.hxml not found at {test_hxml}",
        )

    compiler = HaxeCompiler(config)
    return compiler.compile(test_hxml)
