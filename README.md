# gd-builder

Haxe/Heaps.io build system. Used as a git submodule in game projects.

## Setup

Add as submodule and create symlink:

```bash
git submodule add https://github.com/Lyten02/gd-builder.git modules/gd-builder
cd modules/gd-builder && bash setup.sh
```

This creates `build.py -> modules/gd-builder/build.py` symlink in project root.

## Dependencies

```bash
pip install -r modules/gd-builder/pyproject.toml
# or
pip install click watchdog python-dotenv rich
```

## Usage

```bash
python3 build.py setup              # Install dependencies
python3 build.py build              # Check compilation
python3 build.py test               # Run tests (utest)
python3 build.py run web            # Build and run in browser
python3 build.py run cpp            # Native binary (macOS ARM)
python3 build.py watch web          # Watch mode with live reload
python3 build.py watch web --server server/  # Watch + backend server
python3 build.py build web --gamepush  # Build with GamePush SDK
python3 build.py help               # All commands
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Private tool for Lyten02 projects
