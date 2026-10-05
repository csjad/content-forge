"""Central project paths.

Every module resolves project data/state directories through this module so a
rename or restructure of the package never silently breaks path resolution.
"""
from __future__ import annotations

import os
from pathlib import Path

# contentforge/utils/paths.py -> parents[0]=utils, [1]=contentforge, [2]=project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
STATE_DIR = PROJECT_ROOT / "state"
LOGS_DIR = STATE_DIR / "logs"
BROWSER_STATE_DIR = STATE_DIR / "browser"
DB_PATH = STATE_DIR / "forge.db"


def ensure_dirs() -> None:
    """Create the standard project directories (data, state, logs...)."""
    for d in (DATA_DIR, STATE_DIR, LOGS_DIR, BROWSER_STATE_DIR,
              DATA_DIR / "topics", DATA_DIR / "scripts", DATA_DIR / "videos",
              DATA_DIR / "covers", DATA_DIR / "slides", DATA_DIR / "audio",
              DATA_DIR / "publish", DATA_DIR / "demo", DATA_DIR / "bgm"):
        d.mkdir(parents=True, exist_ok=True)


def get_data_dir() -> Path:
    """Allow tests to override the data root via the FORGE_DATA env var."""
    override = os.environ.get("FORGE_DATA")
    return Path(override) if override else DATA_DIR


def get_state_dir() -> Path:
    """Allow tests to override the state root via the FORGE_STATE env var."""
    override = os.environ.get("FORGE_STATE")
    return Path(override) if override else STATE_DIR
