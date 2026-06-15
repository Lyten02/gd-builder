"""Setup command implementation"""

from ..config import ProjectConfig
from ..services.haxe import collect_haxe_libs
from ..utils.logger import log_step, log_success, log_info, log_warn
from ..utils.process import run_command, check_command_exists


def _haxelib_package_name(lib: str) -> str:
    return lib.split(":", 1)[0].strip()


def _setup_haxe_libs(config: ProjectConfig) -> list[str]:
    libs: list[str] = []
    seen: set[str] = set()
    for raw_lib in [*collect_haxe_libs(config), "utest"]:
        lib = _haxelib_package_name(raw_lib)
        if lib and lib not in seen:
            libs.append(lib)
            seen.add(lib)
    return libs


def setup_command(config: ProjectConfig) -> bool:
    """Install dependencies"""

    log_step("Checking dependencies...")

    # Check Haxe
    if check_command_exists("haxe"):
        result = run_command(["haxe", "--version"])
        log_success(f"Haxe: {result.stdout.strip()}")
    else:
        log_warn("Haxe not found. Install from https://haxe.org/download/")

    # Check HashLink
    if check_command_exists("hl"):
        result = run_command(["hl", "--version"])
        log_success(f"HashLink: {result.stdout.strip()}")
    else:
        log_warn("HashLink not found. Install: brew install hashlink")

    # Check Node.js
    if check_command_exists("node"):
        result = run_command(["node", "--version"])
        log_success(f"Node.js: {result.stdout.strip()}")
    else:
        log_warn("Node.js not found. Install from https://nodejs.org/")

    # Install Haxe libraries
    log_step("Installing Haxe libraries...")

    libs = _setup_haxe_libs(config)
    for lib in libs:
        result = run_command(["haxelib", "path", lib])
        if not result.success:
            log_info(f"Installing {lib}...")
            run_command(["haxelib", "install", lib])
        else:
            log_success(f"{lib} installed")

    # Check for React UI
    ui_dir = config.ui_dir
    if ui_dir.exists():
        node_modules = ui_dir / "node_modules"
        if not node_modules.exists():
            log_step("Installing React dependencies...")
            run_command(["npm", "install"], cwd=ui_dir)
        else:
            log_success("React dependencies installed")

    log_success("Setup complete!")
    return True
