"""`screenshot` and `source` — pull pixels / raw page source off the device."""

from __future__ import annotations

import argparse
import time

from appium_pilot import config
from appium_pilot.output import emit, raw
from appium_pilot.resolve import find_ref
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    sh = sub.add_parser("screenshot", help="save a PNG of the screen (or an element) and print its path")
    sh.add_argument("ref", nargs="?", help="optional element ref to screenshot instead of the screen")
    sh.add_argument("-o", "--out", help="output path (default: session screenshots dir)")
    sh.set_defaults(func=run_screenshot)

    src = sub.add_parser("source", help="print the full raw page source")
    src.set_defaults(func=run_source)


def run_screenshot(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()

    if args.out:
        path = args.out
    else:
        shots = config.screenshots_dir()
        shots.mkdir(parents=True, exist_ok=True)
        path = str(shots / f"shot-{time.strftime('%Y%m%d-%H%M%S')}.png")

    if args.ref:
        locator = session.locator_for(args.ref)
        element = find_ref(driver, locator, args.ref)
        element.screenshot(path)
    else:
        driver.get_screenshot_as_file(path)

    emit(path, path=path)


def run_source(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    raw(driver.page_source)
