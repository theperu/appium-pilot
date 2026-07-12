"""Filesystem layout and shared constants for appium-pilot state."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPIUM_PILOT_HOME", Path.home() / ".appium-pilot"))
SESSIONS_DIR = APP_DIR / "sessions"
SERVER_FILE = APP_DIR / "server.json"

# Default port we start the managed Appium server on.
DEFAULT_APPIUM_PORT = 4723

# Implicit wait (seconds) applied to element finds so they retry on async UIs.
IMPLICIT_WAIT = 5.0

# newCommandTimeout (seconds) for created sessions — long, so the session
# survives between one-shot CLI invocations. The Appium server is the daemon.
NEW_COMMAND_TIMEOUT = 3600


def session_file(name: str) -> Path:
    return SESSIONS_DIR / f"{name}.json"


def ensure_dirs() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# Artifacts (screenshots, videos) land under the *current working directory* so
# they're easy to find — unlike session state, they don't need a fixed location.
# Override the root with APPIUM_PILOT_OUTPUT.
def output_dir() -> Path:
    root = os.environ.get("APPIUM_PILOT_OUTPUT")
    return Path(root) if root else Path.cwd() / "appium-pilot"


def screenshots_dir() -> Path:
    return output_dir() / "screenshots"


def videos_dir() -> Path:
    return output_dir() / "videos"


def diffs_dir() -> Path:
    # Visual-diff images from `expect --baseline` land here (baselines themselves
    # live wherever the user points --baseline, as committed goldens).
    return output_dir() / "diffs"
