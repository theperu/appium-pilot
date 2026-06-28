"""`devices` — list available simulators/emulators."""

from __future__ import annotations

import argparse

from appium_pilot import devices
from appium_pilot.output import emit, json_mode


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("devices", help="list available iOS simulators / Android emulators")
    p.set_defaults(func=run)


def run(args) -> None:
    found = devices.list_all()
    payload = [
        {"platform": d.platform, "udid": d.udid, "name": d.name, "booted": d.booted}
        for d in found
    ]
    if json_mode():
        emit(f"{len(found)} devices", devices=payload)
        return
    if not found:
        emit("no devices found (no booted simulators/emulators or AVDs)")
        return
    for d in found:
        state = "booted" if d.booted else "available"
        print(f"{d.platform:8} {state:10} {d.name}  ({d.udid})")
