"""CLI definition using Click"""

from __future__ import annotations

import sys
import click
from pathlib import Path
from typing import Optional

from .config import ProjectConfig, get_config, set_config
from .utils.logger import log_info, log_error, log_paths, log_warn


# Custom type for mode validation
class ModeType(click.Choice):
    """Mode type that requires explicit debug/release"""
    name = "mode"

    def __init__(self):
        super().__init__(["debug", "release"])


# Custom type for platform validation
class PlatformType(click.Choice):
    """Platform type"""
    name = "platform"

    def __init__(self, include_all: bool = False):
        choices = ["web", "cpp"]
        if include_all:
            choices.append("all")
        super().__init__(choices)


def common_options(f):
    """Common options for all commands"""
    f = click.option("--verbose", "-v", is_flag=True, help="Verbose output")(f)
    f = click.pass_context(f)
    return f


def build_options(f):
    """Options for build-related commands"""
    f = click.option("--gamepush", is_flag=True, help="Enable GamePush SDK")(f)
    return f


@click.group()
@click.version_option(version="1.0.0", prog_name="Haxe Builder")
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path),
              help="Project root directory")
@click.pass_context
def cli(ctx, project_dir: Path | None):
    """Haxe/Heaps Build System

    All build commands require MODE (debug/release) as first argument.

    Examples:

        build.py build debug web

        build.py run release cpp

        build.py watch debug web --react

        build.py test debug

        build.py publish release web --netlify
    """
    ctx.ensure_object(dict)
    ctx.obj["project_dir"] = project_dir


@cli.command()
@click.argument("mode", type=ModeType())
@click.argument("platform", type=PlatformType(include_all=True), default="web")
@build_options
@common_options
def build(ctx, mode: str, platform: str, gamepush: bool, verbose: bool):
    """Build the project

    MODE: debug or release (required)

    PLATFORM: web, cpp, or all (default: web)
    """
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, gamepush=gamepush, verbose=verbose)
    log_paths(str(config.project_dir), str(config.starter_dir) if config.starter_dir else None)

    from .commands.build import build_command
    success = build_command(config, mode, platform)
    sys.exit(0 if success else 1)


@cli.command()
@click.argument("mode", type=ModeType())
@click.argument("platform", type=PlatformType(), default="web")
@build_options
@common_options
def run(ctx, mode: str, platform: str, gamepush: bool, verbose: bool):
    """Build and run the project

    MODE: debug or release (required)

    PLATFORM: web or cpp (default: web)
    """
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, gamepush=gamepush, verbose=verbose)
    log_paths(str(config.project_dir), str(config.starter_dir) if config.starter_dir else None)

    from .commands.run import run_command
    success = run_command(config, mode, platform)
    sys.exit(0 if success else 1)


@cli.command()
@click.argument("mode", type=ModeType())
@click.argument("platform", type=PlatformType(), default="web")
@click.option("--react", is_flag=True, help="React UI mode (Vite + Haxe API)")
@click.option("--netlify", is_flag=True, help="Deploy to Netlify on change")
@click.option("--port", "-p", type=int, default=None, help="Web server port (or Vite port in --react mode)")
@click.option("--server", default=None, is_flag=False, flag_value="server/",
              help="Start backend server(s). Comma-separated: --server api/,ws/")
@build_options
@common_options
def watch(ctx, mode: str, platform: str, react: bool, netlify: bool, port: Optional[int],
          server: Optional[str], gamepush: bool, verbose: bool):
    """Watch for changes and rebuild

    MODE: debug or release (required)

    PLATFORM: web or cpp (default: web)
    """
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, gamepush=gamepush, verbose=verbose,
                           react_mode=react, netlify_deploy=netlify,
                           servers=server)
    if port is not None:
        config.serve_port = port
    log_paths(str(config.project_dir), str(config.starter_dir) if config.starter_dir else None)

    from .commands.watch import watch_command
    success = watch_command(config, mode, platform)
    sys.exit(0 if success else 1)


@cli.command()
@click.argument("mode", type=ModeType())
@click.argument("platform", type=PlatformType(include_all=True), default="web")
@click.option("--react", is_flag=True, help="React UI mode (Vite + Haxe API)")
@click.option("--netlify", is_flag=True, help="Deploy to Netlify")
@build_options
@common_options
def publish(ctx, mode: str, platform: str, react: bool, netlify: bool, gamepush: bool,
            verbose: bool):
    """Create release build and package

    MODE: debug or release (required)

    PLATFORM: web, cpp, or all (default: web)
    """
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, gamepush=gamepush, verbose=verbose,
                           react_mode=react, netlify_deploy=netlify)
    log_paths(str(config.project_dir), str(config.starter_dir) if config.starter_dir else None)

    from .commands.publish import publish_command
    success = publish_command(config, mode, platform)
    sys.exit(0 if success else 1)


@cli.command()
@common_options
def test(ctx, verbose: bool):
    """Run tests"""
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, verbose=verbose)
    log_paths(str(config.project_dir), str(config.starter_dir) if config.starter_dir else None)

    from .commands.test import test_command
    success = test_command(config)
    sys.exit(0 if success else 1)


@cli.command()
@common_options
def clean(ctx, verbose: bool):
    """Clean build artifacts"""
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, verbose=verbose)

    from .commands.clean import clean_command
    success = clean_command(config)
    sys.exit(0 if success else 1)


@cli.command()
@common_options
def setup(ctx, verbose: bool):
    """Install dependencies"""
    project_dir = ctx.obj.get("project_dir")
    config = _setup_config(project_dir, verbose=verbose)

    from .commands.setup import setup_command
    success = setup_command(config)
    sys.exit(0 if success else 1)


def _setup_config(
    project_dir: Path | None = None,
    gamepush: bool = False,
    verbose: bool = False,
    react_mode: bool = False,
    netlify_deploy: bool = False,
    servers: str | None = None,
) -> ProjectConfig:
    """Setup and return project config"""
    config = ProjectConfig.from_project_root(project_dir)
    config.gamepush_enabled = gamepush
    config.verbose = verbose
    config.react_mode = react_mode
    config.netlify_deploy = netlify_deploy
    config.servers = _parse_servers(servers, config.project_dir)
    set_config(config)
    return config


def _parse_servers(servers: str | None, project_dir: Path) -> list[Path]:
    """Parse comma-separated server directories"""
    if not servers:
        return []

    result = []
    for server in servers.split(","):
        server = server.strip()
        if server:
            server_path = project_dir / server
            if server_path.exists():
                result.append(server_path)
            else:
                log_warn(f"Server directory not found: {server_path}")
    return result


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
