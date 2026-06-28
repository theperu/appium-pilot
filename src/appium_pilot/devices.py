"""Device/simulator discovery and boot for iOS Simulator + Android Emulator.

v1 policy: auto-pick a booted device → else boot a sensible default →
`--device` overrides. `devices` lists what's available.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from appium_pilot import proc
from appium_pilot.output import CommandError


@dataclass
class Device:
    platform: str  # "android" | "ios"
    udid: str
    name: str
    booted: bool


def _run(cmd: list[str], timeout: float = 30.0) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout


def _sdk_root() -> Optional[Path]:
    root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    return Path(root) if root else None


def android_tool(name: str) -> Optional[str]:
    """Resolve an Android SDK tool from PATH, else from $ANDROID_HOME subdirs."""
    found = shutil.which(name)
    if found:
        return found
    root = _sdk_root()
    if not root:
        return None
    # On Windows the binaries carry extensions (adb.exe, sdkmanager.bat, ...).
    exts = ("", ".exe", ".bat", ".cmd") if os.name == "nt" else ("",)
    for sub in ("platform-tools", "emulator", "tools/bin", "cmdline-tools/latest/bin"):
        for ext in exts:
            candidate = root / sub / (name + ext)
            if candidate.exists():
                return str(candidate)
    return None


# --------------------------------------------------------------------------- iOS


def ios_booted() -> list[Device]:
    if not shutil.which("xcrun"):
        return []
    out = _run(["xcrun", "simctl", "list", "devices", "booted", "-j"])
    data = json.loads(out or "{}")
    devices: list[Device] = []
    for runtime_devs in data.get("devices", {}).values():
        for d in runtime_devs:
            if d.get("state") == "Booted":
                devices.append(Device("ios", d["udid"], d.get("name", "?"), True))
    return devices


def ios_available() -> list[Device]:
    if not shutil.which("xcrun"):
        return []
    out = _run(["xcrun", "simctl", "list", "devices", "available", "-j"])
    data = json.loads(out or "{}")
    devices: list[Device] = []
    for runtime_devs in data.get("devices", {}).values():
        for d in runtime_devs:
            if d.get("isAvailable", True):
                booted = d.get("state") == "Booted"
                devices.append(Device("ios", d["udid"], d.get("name", "?"), booted))
    return devices


def ios_boot_default() -> Device:
    candidates = ios_available()
    pick = next((d for d in candidates if d.name.startswith("iPhone")), None) or (
        candidates[0] if candidates else None
    )
    if pick is None:
        raise CommandError("no iOS simulators available; create one in Xcode first")
    if not pick.booted:
        _run(["xcrun", "simctl", "boot", pick.udid])
        time.sleep(2)
        pick.booted = True
    return pick


# ----------------------------------------------------------------------- Android


def android_booted() -> list[Device]:
    adb = android_tool("adb")
    if not adb:
        return []
    out = _run([adb, "devices"])
    devices: list[Device] = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(Device("android", parts[0], parts[0], True))
    return devices


def android_avds() -> list[str]:
    emulator = android_tool("emulator")
    if not emulator:
        return []
    out = _run([emulator, "-list-avds"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def android_boot_default() -> Device:
    booted = android_booted()
    if booted:
        return booted[0]
    avds = android_avds()
    if not avds:
        raise CommandError("no Android emulators (AVDs) available; create one with avdmanager")
    emulator = android_tool("emulator")
    adb = android_tool("adb")
    subprocess.Popen(
        [emulator, "-avd", avds[0]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **proc.detach_kwargs(),
    )
    # Wait for the device to come online and finish booting.
    deadline = time.time() + 180
    while time.time() < deadline:
        booted = android_booted()
        if booted:
            _run([adb, "wait-for-device"], timeout=180)
            for _ in range(60):
                if _run([adb, "shell", "getprop", "sys.boot_completed"]).strip() == "1":
                    return booted[0]
                time.sleep(2)
            return booted[0]
        time.sleep(2)
    raise CommandError(f"emulator '{avds[0]}' did not come online within 180s")


# ------------------------------------------------------------------------ resolve


def resolve(platform: str, requested: Optional[str]) -> Device:
    """Pick the device to drive: explicit --device, else booted, else boot default."""
    booted = ios_booted() if platform == "ios" else android_booted()

    if requested:
        for d in booted:
            if requested in (d.udid, d.name):
                return d
        # Not currently booted — for iOS we can boot a named/udid simulator.
        if platform == "ios":
            for d in ios_available():
                if requested in (d.udid, d.name):
                    _run(["xcrun", "simctl", "boot", d.udid])
                    time.sleep(2)
                    d.booted = True
                    return d
        raise CommandError(f"device '{requested}' not found or not booted")

    if booted:
        return booted[0]

    return ios_boot_default() if platform == "ios" else android_boot_default()


def list_all() -> list[Device]:
    return ios_available() + android_booted() + [
        Device("android", a, a, False) for a in android_avds()
    ]
