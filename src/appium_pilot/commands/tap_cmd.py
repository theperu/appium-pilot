"""`tap` — tap a target (ref, text, or coordinate), optionally long/double.

By ref is the default and most robust path. `--text` covers elements the filter
misses or that the agent knows by label; `--at x,y` is the raw coordinate escape
hatch. `--long`/`--double` change the gesture for any of the three targets.
"""

from __future__ import annotations

import argparse

from appium_pilot.output import CommandError, emit
from appium_pilot.resolve import find_ref
from appium_pilot.session import Session

_VERB = {"single": "tapped", "long": "long-pressed", "double": "double-tapped"}


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("tap", help="tap an element (by ref or --text) or a coordinate (--at)")
    p.add_argument("ref", nargs="?", help="element ref from the latest snapshot, e.g. e7")
    p.add_argument("--text", help="tap the first element whose visible text matches")
    p.add_argument("--at", metavar="X,Y", help="tap raw coordinates, e.g. --at 200,640")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--long", action="store_true", help="long-press instead of a tap")
    mode.add_argument("--double", action="store_true", help="double-tap instead of a tap")
    p.add_argument("--duration", type=float, default=1.0,
                   help="long-press duration in seconds (default 1.0; --long only)")
    p.set_defaults(func=run)


def _parse_xy(spec: str) -> tuple[int, int]:
    try:
        x, y = (int(part) for part in spec.replace(" ", "").split(","))
    except ValueError as exc:
        raise CommandError(f"bad --at {spec!r}; expected two integers 'x,y'") from exc
    return x, y


def run(args) -> None:
    if sum(bool(t) for t in (args.ref, args.text, args.at)) != 1:
        raise CommandError("tap needs exactly one of: a ref, --text <s>, or --at x,y")

    kind = "long" if args.long else "double" if args.double else "single"
    session = Session.load(args.session)
    driver = session.attach()
    strategy = session.strategy

    if args.at:
        x, y = _parse_xy(args.at)
        strategy.gesture_tap(driver, kind, x=x, y=y, duration=args.duration)
        emit(f"{_VERB[kind]} at ({x},{y})", x=x, y=y)
        return

    if args.text:
        element = strategy.find_by_text(driver, args.text)
        if element is None:
            raise CommandError(f"no element found with text {args.text!r}", code=2)
        target_desc, payload = f'text "{args.text}"', {"text": args.text}
    else:
        locator = session.locator_for(args.ref)
        element = find_ref(driver, locator, args.ref)
        label = f' "{locator.text}"' if locator.text else ""
        target_desc, payload = f"{args.ref}{label}", {"ref": args.ref}

    if kind == "single":
        element.click()
    else:
        strategy.gesture_tap(driver, kind, element=element, duration=args.duration)
    emit(f"{_VERB[kind]} {target_desc}", **payload)
