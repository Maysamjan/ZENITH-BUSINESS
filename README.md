# Zenith Business

Offline business management and accounting system, developed under the
**Zenith Soft** brand.

> **Stage 01 — Project Foundation.** This repository currently contains the
> application *foundation* only: the shell, core infrastructure, and a testing
> base. No business modules (accounting, inventory, sales, ...) are implemented
> yet. See [`PROJECT_MASTER.md`](PROJECT_MASTER.md) for the architecture and
> module status.

## Requirements

- Python **3.12+** recommended (code is 3.11-compatible for CI/dev).
- PyQt6 (installed automatically as a dependency).
- Windows is the primary target; the app runs on Linux/macOS for development.

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate

# 2. Install the app plus development tools (pytest, pytest-qt)
pip install -e ".[dev]"
```

## Run the application

```bash
python -m zenith_business
# or, after install, the console script:
zenith-business
```

You should see the branded home screen with the **top** navigation bar. Business
menus are present but shown as disabled placeholders (no business features exist
yet). Switch language (English / Dari) from **Tools → Language**; Dari renders
the whole shell right-to-left.

## Run the tests

```bash
pytest
```

UI-shell tests run headlessly using Qt's *offscreen* platform (configured
automatically in `tests/conftest.py`). On a headless Linux box you may need the
Qt runtime libraries, e.g. on Debian/Ubuntu:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3 \
    libglib2.0-0t64 libfontconfig1 libfreetype6
```

## Project structure

```
zenith_business/
    app.py              # startup orchestration + entry point (python -m ...)
    __main__.py         # enables `python -m zenith_business`
    core/               # identity, config, paths, logging, errors, i18n
    database/           # SQLite connection, transactions, health (NO business tables)
    security/           # password hashing + licensing architecture boundary
    ui/                 # application shell (top nav, home, status bar)
        design/         # centralized design system (tokens + QSS theme)
    resources/          # static assets (logo placeholder)
tests/                  # pytest foundation
pyproject.toml          # dependencies + build + pytest config
PROJECT_MASTER.md       # authoritative development memory
```

## Configuration & data locations

Application **code** is kept separate from **user/business data** (Prompt 01 §5,
§30). Writable data never lives in the install directory:

| Data | Windows location |
|------|------------------|
| Configuration | `%APPDATA%\ZenithSoft\ZenithBusiness\config\` |
| License state | `%APPDATA%\ZenithSoft\ZenithBusiness\license\` |
| Database | `%LOCALAPPDATA%\ZenithSoft\ZenithBusiness\data\` |
| Logs | `%LOCALAPPDATA%\ZenithSoft\ZenithBusiness\logs\` |
| Backups | `%LOCALAPPDATA%\ZenithSoft\ZenithBusiness\backups\` |

On non-Windows dev machines, equivalents under `~/.config` and `~/.local/share`
are used. Set the `ZENITH_DATA_HOME` environment variable to redirect all of the
above to a single sandbox (used by the test suite).

## License

Proprietary — © Zenith Soft. All rights reserved.
