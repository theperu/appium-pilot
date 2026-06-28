"""Appium server lifecycle.

The Appium server is our daemon: it holds the live WebDriver sessions between
one-shot CLI invocations. We auto-start one in the background on demand and
reuse it, tracking {pid, port} in SERVER_FILE.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional

from appium_pilot import config, proc
from appium_pilot.output import CommandError


def _status_ok(base_url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/status", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _read_server_file() -> Optional[dict]:
    if config.SERVER_FILE.exists():
        try:
            return json.loads(config.SERVER_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def ensure_server(port: int = config.DEFAULT_APPIUM_PORT) -> str:
    """Return the base URL of a running managed Appium server, starting one if needed."""
    existing = _read_server_file()
    if existing and _status_ok(_base_url(existing["port"])):
        return _base_url(existing["port"])

    if _status_ok(_base_url(port)):
        # A server is already listening (started by us earlier or by the user).
        config.ensure_dirs()
        config.SERVER_FILE.write_text(json.dumps({"pid": None, "port": port}))
        return _base_url(port)

    return _start_server(port)


def _start_server(port: int) -> str:
    config.ensure_dirs()
    log_path = config.APP_DIR / "appium-server.log"
    argv = proc.tool("appium", "--port", str(port), "--log-timestamp", "--base-path", "/")
    if argv is None:
        raise CommandError(
            "appium server not found on PATH. Install it with `npm i -g appium` "
            "(see `appium-pilot doctor`)."
        )
    log_file = open(log_path, "ab")
    server = subprocess.Popen(
        argv,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        **proc.detach_kwargs(),  # detach so it outlives this one-shot CLI run
    )

    base = _base_url(port)
    deadline = time.time() + 30
    while time.time() < deadline:
        if _status_ok(base):
            config.SERVER_FILE.write_text(json.dumps({"pid": server.pid, "port": port}))
            return base
        if server.poll() is not None:
            raise CommandError(f"appium server exited during startup; see {log_path}")
        time.sleep(0.5)

    raise CommandError(f"appium server did not become ready within 30s; see {log_path}")
