"""`type` and `clear` — text entry into a referenced element."""

from __future__ import annotations

import argparse

from appium_pilot.output import CommandError, emit
from appium_pilot.resolve import find_ref
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("type", help="type text into the element referenced by a ref")
    p.add_argument("ref", help="element ref from the latest snapshot")
    p.add_argument("text", help="text to type")
    p.add_argument("--clear", action="store_true", help="clear existing text first")
    p.add_argument("--submit", action="store_true", help="press enter/return after typing")
    p.set_defaults(func=run_type)

    c = sub.add_parser("clear", help="clear text from the element referenced by a ref")
    c.add_argument("ref", help="element ref from the latest snapshot")
    c.set_defaults(func=run_clear)


def _editable(element) -> bool:  # noqa: ANN001
    # Best-effort guard; not all drivers expose this attribute.
    try:
        return element.get_attribute("enabled") != "false"
    except Exception:  # noqa: BLE001
        return True


def run_type(args) -> None:
    session = Session.load(args.session)
    locator = session.locator_for(args.ref)
    driver = session.attach()
    element = find_ref(driver, locator, args.ref)
    if not _editable(element):
        raise CommandError(f"ref {args.ref} is not editable")
    if args.clear:
        element.clear()
    element.send_keys(args.text)
    if args.submit:
        session.strategy.submit(driver, element)
    emit(f"typed into {args.ref}" + (" (submitted)" if args.submit else ""), ref=args.ref)


def run_clear(args) -> None:
    session = Session.load(args.session)
    locator = session.locator_for(args.ref)
    driver = session.attach()
    element = find_ref(driver, locator, args.ref)
    element.clear()
    emit(f"cleared {args.ref}", ref=args.ref)
