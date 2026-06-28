"""`doctor` — diagnose the environment. Never installs anything."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

from appium_pilot import config, proc
from appium_pilot.output import emit, json_mode


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("doctor", help="diagnose Appium/iOS/Android setup (does not install)")
    p.set_defaults(func=run)


def _version(name: str, *args: str) -> str | None:
    argv = proc.tool(name, *args)
    if argv is None:
        return None
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        return (out.stdout or out.stderr).strip().splitlines()[0] if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _appium_drivers() -> set[str]:
    argv = proc.tool("appium", "driver", "list", "--installed", "--json")
    if argv is None:
        return set()
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout or out.stderr or "{}")
        return set(data.keys())
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return set()


def run(args) -> None:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str, hint: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail, "hint": hint})

    # Core toolchain.
    node = _version("node", "--version")
    check("node", node is not None, node or "not found", "install Node.js")
    npm = _version("npm", "--version")
    check("npm", npm is not None, npm or "not found", "install Node.js (bundles npm)")
    appium = _version("appium", "--version")
    check("appium server", appium is not None, appium or "not found", "npm i -g appium")

    drivers = _appium_drivers() if appium else set()
    check("uiautomator2 driver", "uiautomator2" in drivers,
          "installed" if "uiautomator2" in drivers else "missing",
          "appium driver install uiautomator2")
    check("xcuitest driver", "xcuitest" in drivers,
          "installed" if "xcuitest" in drivers else "missing",
          "appium driver install xcuitest")

    # iOS.
    xcrun = shutil.which("xcrun")
    check("xcode command line tools (xcrun)", xcrun is not None,
          xcrun or "not found", "xcode-select --install")

    # Android.
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    check("ANDROID_HOME / ANDROID_SDK_ROOT", bool(android_home),
          android_home or "not set", "export ANDROID_HOME=~/Library/Android/sdk")
    from appium_pilot import devices

    adb = devices.android_tool("adb")
    check("adb", adb is not None, adb or "not found", "install Android platform-tools")
    emulator = devices.android_tool("emulator")
    check("emulator", emulator is not None, emulator or "not found", "install Android emulator package")

    # Stale state.
    server_running = config.SERVER_FILE.exists()
    session_count = len(list(config.SESSIONS_DIR.glob("*.json"))) if config.SESSIONS_DIR.exists() else 0
    check("managed appium server record", True,
          "present" if server_running else "none",
          "`appium-pilot kill-all` clears stale server/session state")
    check("persisted sessions", True, f"{session_count} on disk",
          "`appium-pilot list` to inspect, `close-all` to clear")

    if json_mode():
        ok = all(c["ok"] for c in checks)
        emit("doctor complete", ok=ok, checks=checks)
        return

    for c in checks:
        mark = "✓" if c["ok"] else "✗"
        line = f"  {mark} {c['name']}: {c['detail']}"
        if not c["ok"] and c["hint"]:
            line += f"\n      → {c['hint']}"
        print(line)
    missing = [c for c in checks if not c["ok"]]
    print()
    print("doctor: all good" if not missing else f"doctor: {len(missing)} item(s) need attention")
