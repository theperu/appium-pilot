"""`get` — read a ref's current live state without a full re-snapshot.

The cheap way to confirm state after acting (e.g. that a field now holds the
text you typed): resolve the ref live and read its attributes, instead of paying
for a whole new snapshot + ref renumber.
"""

from __future__ import annotations

import argparse

from appium_pilot.output import emit
from appium_pilot.resolve import find_ref
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("get", help="read a ref's current text/value/enabled state")
    p.add_argument("ref", help="element ref from the latest snapshot")
    p.add_argument("attr", nargs="?",
                   help="a single attribute to read raw (e.g. bounds, focused); "
                        "omit for a state summary")
    p.set_defaults(func=run)


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f'"{value}"'


def run(args) -> None:
    session = Session.load(args.session)
    locator = session.locator_for(args.ref)
    driver = session.attach()
    element = find_ref(driver, locator, args.ref)

    if args.attr:
        value = element.get_attribute(args.attr)
        emit(f"{args.ref}.{args.attr} = {value}", ref=args.ref, attr=args.attr, value=value)
        return

    state = session.strategy.element_state(element)
    summary = " ".join(f"{k}={_fmt(v)}" for k, v in state.items())
    emit(f"{args.ref}: {summary}", ref=args.ref, **state)
