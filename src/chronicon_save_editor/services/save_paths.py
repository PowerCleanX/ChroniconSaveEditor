from __future__ import annotations

import os
from pathlib import Path


LAST_OPEN_DIR_KEY = "ui/last_open_dir"


def discover_chronicon_save_dir() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "Chronicon" / "save"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def choose_initial_open_dir(last_open_dir: str | None) -> Path:
    if last_open_dir:
        candidate = Path(last_open_dir)
        if candidate.exists() and candidate.is_dir():
            return candidate

    discovered = discover_chronicon_save_dir()
    if discovered is not None:
        return discovered

    return Path.home()
