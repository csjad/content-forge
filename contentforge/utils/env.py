"""Environment variable loading: reads a ``.env`` file from the project root.

Simple parser — no external dependency. Values already present in the process
environment win over the file.
"""
from __future__ import annotations

import os

from .paths import PROJECT_ROOT


def load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


load_dotenv()
