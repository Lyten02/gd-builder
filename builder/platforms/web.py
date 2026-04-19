"""Web platform implementation"""

import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .base import BasePlatform
from ..config import ProjectConfig
from ..utils.logger import log_step, log_success, log_info


class WebPlatform(BasePlatform):
    """Web platform (JavaScript output)"""

    @property
    def name(self) -> str:
        return "web"

    @property
    def output_dir(self) -> Path:
        return self.config.get_web_dir(self.mode)

    def prepare(self) -> bool:
        """Create output directory"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return True

    def post_build(self) -> bool:
        """Copy resources, create index.html, generate version.json"""
        # Copy resources
        if self.config.res_dir.exists():
            res_dest = self.output_dir / "res"
            if res_dest.exists():
                shutil.rmtree(res_dest)
            shutil.copytree(self.config.res_dir, res_dest)

        # Create index.html if not exists
        index_path = self.output_dir / "index.html"
        if not index_path.exists():
            self._create_index_html(index_path)

        # Generate version.json
        self._generate_version_json()

        # Copy game.js to ui/public/watch/ only in explicit React watch/dev mode.
        # Regular `build debug web` should not overwrite React watch artifacts.
        if self.mode == "debug" and self.config.react_mode and self.config.ui_dir.exists():
            watch_dir = self.config.ui_dir / "public" / "watch"
            watch_dir.mkdir(parents=True, exist_ok=True)
            game_js = self.output_dir / "game.js"
            if game_js.exists():
                shutil.copy(game_js, watch_dir / "game.js")
                log_info("Copied game.js to ui/public/watch/")

        return True

    def run(self) -> bool:
        """Open in browser"""
        import platform as plt
        index_path = self.output_dir / "index.html"

        if not index_path.exists():
            self._create_index_html(index_path)

        log_success(f"Opening {index_path}")

        if plt.system() == "Darwin":
            subprocess.run(["open", str(index_path)])
        elif shutil.which("xdg-open"):
            subprocess.run(["xdg-open", str(index_path)])

        return True

    def _create_index_html(self, path: Path) -> None:
        """Create index.html for the game"""
        gamepush_script = ""
        game_script = '<script src="game.js"></script>'

        if self.config.gamepush_enabled:
            build_ts = int(time.time())
            gp_id = self.config.gp_project_id or ""
            gp_token = self.config.gp_public_token or ""

            gamepush_script = f'''
    <script>
        window.gamePushReady = false;
        window.onGPInit = async (gp) => {{
            console.log('[Loader] GamePush SDK initialized');
            window.gamePushSDK = gp;
            await gp.player.ready;
            console.log('[Loader] Player ready, loading game.js...');
            window.gamePushReady = true;
            var s = document.createElement('script');
            s.src = 'game.js?v={build_ts}';
            s.onload = function() {{
                console.log('[Loader] game.js loaded, dispatching gamepush-ready');
                window.dispatchEvent(new Event('gamepush-ready'));
            }};
            s.onerror = function(e) {{ console.error('[Loader] game.js failed', e); }};
            document.body.appendChild(s);
        }};
    </script>
    <script async src="https://gamepush.com/sdk/game-score.js?projectId={gp_id}&publicToken={gp_token}&callback=onGPInit"></script>'''
            game_script = ""

        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>Haxe Game</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; background: #000; position: fixed; top: 0; left: 0; }}
        #game-container {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }}
        #webgl {{ display: block; width: 100%; height: 100%; touch-action: none; }}
        #loading {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #fff; font-family: Arial, sans-serif; font-size: 24px; z-index: 100; }}
        #update-notice {{ position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(46, 204, 113, 0.95); color: white; padding: 12px 24px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 14px; z-index: 1000; display: none; cursor: pointer; }}
    </style>
</head>
<body>
    <div id="loading">Loading...</div>
    <div id="update-notice" onclick="location.reload()">New version available! Click to reload</div>
    <div id="game-container">
        <canvas id="webgl"></canvas>
    </div>
    <script>
        var isResizing = false;
        function fixViewport() {{
            var canvas = document.getElementById('webgl');
            var container = document.getElementById('game-container');
            container.style.width = window.innerWidth + 'px';
            container.style.height = window.innerHeight + 'px';
            canvas.style.width = window.innerWidth + 'px';
            canvas.style.height = window.innerHeight + 'px';
        }}
        window.addEventListener('resize', function() {{
            if (isResizing) return;
            isResizing = true;
            fixViewport();
            setTimeout(function(){{ isResizing = false; }}, 10);
        }});
        window.onload = function() {{
            document.getElementById('loading').style.display = 'none';
            fixViewport();
        }};

        (function() {{
            var currentVersion = null;
            var isLocalDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
            var checkInterval = isLocalDev ? 100 : 30000;
            var autoReload = isLocalDev;

            function checkForUpdates() {{
                fetch('version.json?_=' + Date.now())
                    .then(r => r.ok ? r.json() : null)
                    .then(data => {{
                        if (data && data.version) {{
                            if (currentVersion === null) currentVersion = data.version;
                            else if (currentVersion !== data.version) handleUpdate();
                        }}
                    }}).catch(() => {{}});
            }}
            function handleUpdate() {{
                if (autoReload) location.reload();
                else {{ var n = document.getElementById('update-notice'); if (n) n.style.display = 'block'; }}
            }}
            setInterval(checkForUpdates, checkInterval);
            checkForUpdates();
        }})();
    </script>
{gamepush_script}
    {game_script}
</body>
</html>'''

        path.write_text(html)

    def _generate_version_json(self) -> None:
        """Generate version.json for auto-reload"""
        version_hash = hashlib.md5(str(time.time_ns()).encode()).hexdigest()

        # Try to get git commit
        git_commit = "unknown"
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.config.project_dir,
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except Exception:
            pass

        build_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        version_data = {
            "version": version_hash,
            "commit": git_commit,
            "buildTime": build_time,
        }

        version_path = self.output_dir / "version.json"
        version_path.write_text(json.dumps(version_data))
