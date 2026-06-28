"""Cross-platform helpers for invoking external tools.

The tricky cases are all Windows: npm-installed CLIs (`appium`, `npm`) are batch
shims (`.cmd`) that CreateProcess can't launch directly, and detaching a
long-lived background process uses creation flags rather than a new session.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

IS_WINDOWS = os.name == "nt"


def which(name: str) -> Optional[str]:
    """Resolve a tool on PATH. On Windows this honors PATHEXT (.exe/.cmd/.bat)."""
    return shutil.which(name)


def tool(name: str, *args: str) -> Optional[list[str]]:
    """Build an argv list to run `name` with `args`, or None if it isn't found.

    Batch shims (.cmd/.bat) are wrapped with `cmd /c` because CreateProcess
    cannot execute them directly.
    """
    resolved = which(name)
    if not resolved:
        return None
    if IS_WINDOWS and resolved.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", resolved, *args]
    return [resolved, *args]


def detach_kwargs() -> dict:
    """Popen kwargs that detach a process so it outlives this one-shot CLI run."""
    if IS_WINDOWS:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": flags}
    return {"start_new_session": True}
