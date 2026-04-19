"""Project configuration and path management"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv


@dataclass
class ProjectConfig:
    """Project configuration loaded from environment and paths"""

    # Paths
    project_dir: Path
    src_dir: Path
    res_dir: Path
    bin_dir: Path
    build_dir: Path
    modules_dir: Path
    ui_dir: Path
    starter_dir: Optional[Path] = None

    # Settings
    project_name: str = "HaxeGame"
    serve_port: int = 5500
    haxe_server_port: int = 6000

    # Backend servers (list of directories)
    servers: list[Path] = field(default_factory=list)

    # Environment
    gp_project_id: Optional[str] = None
    gp_public_token: Optional[str] = None
    netlify_token: Optional[str] = None
    netlify_site_id: Optional[str] = None

    # Feature flags
    gamepush_enabled: bool = False
    react_mode: bool = False
    netlify_deploy: bool = False
    verbose: bool = False

    @classmethod
    def from_project_root(cls, project_dir: Optional[Path] = None) -> "ProjectConfig":
        """Create config from project root directory"""
        if project_dir is None:
            project_dir = cls._find_project_root()

        project_dir = Path(project_dir).resolve()

        # Load .env file
        env_file = project_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

        # Find starter module
        starter_dir = None
        modules_starter = project_dir / "modules" / "starter"
        if modules_starter.exists():
            starter_dir = modules_starter
        else:
            modules_haxeheaps_starter = project_dir / "modules" / "haxeheaps-starter"
            if modules_haxeheaps_starter.exists():
                starter_dir = modules_haxeheaps_starter

        def _env_int(names: list[str], default: int) -> int:
            for name in names:
                raw = os.getenv(name)
                if raw is None or raw.strip() == "":
                    continue
                try:
                    return int(raw)
                except ValueError:
                    continue
            return default

        return cls(
            project_dir=project_dir,
            src_dir=project_dir / "src",
            res_dir=project_dir / "res",
            bin_dir=project_dir / "bin",
            build_dir=project_dir / "build",
            modules_dir=project_dir / "modules",
            ui_dir=project_dir / "ui",
            starter_dir=starter_dir,
            serve_port=_env_int(["SERVE_PORT", "VITE_PORT"], 5500),
            gp_project_id=os.getenv("GP_PROJECT_ID"),
            gp_public_token=os.getenv("GP_PUBLIC_TOKEN"),
            netlify_token=os.getenv("NETLIFY_TOKEN"),
            netlify_site_id=os.getenv("NETLIFY_SITE_ID"),
        )

    @staticmethod
    def _find_project_root() -> Path:
        """Find project root by looking for markers"""
        current = Path.cwd()

        markers = ["src", "build.py", "CLAUDE.md", ".git"]

        for _ in range(10):  # Max 10 levels up
            if any((current / marker).exists() for marker in markers):
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent

        return Path.cwd()

    def get_web_dir(self, mode: str) -> Path:
        """Get web output directory based on mode and gamepush flag"""
        if self.gamepush_enabled:
            return self.bin_dir / "web" / f"{mode}-gamepush"
        return self.bin_dir / "web" / mode

    def get_hxml_path(self, platform: str, mode: str) -> Path:
        """Get path for generated .hxml file"""
        return self.build_dir / f"{platform}_{mode}.hxml"

    def get_main_class(self) -> str:
        """Main class for build"""
        return "Main"

    def get_source_paths(self) -> list[Path]:
        """Get all source paths for compilation"""
        paths = [self.src_dir]

        # Add starter module if present
        if self.starter_dir and (self.starter_dir / "src").exists():
            paths.append(self.starter_dir / "src")

        # Auto-discover modules
        if self.modules_dir.exists():
            for module in self.modules_dir.iterdir():
                if module.is_dir() and module.name not in ("starter", "haxeheaps-starter"):
                    module_src = module / "src"
                    if module_src.exists():
                        paths.append(module_src)

        return paths

    def validate_gamepush(self) -> bool:
        """Validate GamePush configuration"""
        if not self.gamepush_enabled:
            return True
        return bool(self.gp_project_id and self.gp_public_token)

    def validate_netlify(self) -> bool:
        """Validate Netlify configuration"""
        if not self.netlify_deploy:
            return True
        return bool(self.netlify_token)


# Global config instance (lazy loaded)
_config: Optional[ProjectConfig] = None


def get_config() -> ProjectConfig:
    """Get or create global config instance"""
    global _config
    if _config is None:
        _config = ProjectConfig.from_project_root()
    return _config


def set_config(config: ProjectConfig) -> None:
    """Set global config instance (for testing)"""
    global _config
    _config = config
