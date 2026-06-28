"""`tap` — re-find a ref's element live and tap it."""

from __future__ import annotations

import argparse

from appium_pilot.output import emit
from appium_pilot.resolve import find_ref
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("tap", help="tap the element referenced by a snapshot ref")
    p.add_argument("ref", help="element ref from the latest snapshot, e.g. e7")
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    locator = session.locator_for(args.ref)
    driver = session.attach()
    element = find_ref(driver, locator, args.ref)
    element.click()
    label = f' "{locator.text}"' if locator.text else ""
    emit(f"tapped {args.ref}{label}", ref=args.ref)
