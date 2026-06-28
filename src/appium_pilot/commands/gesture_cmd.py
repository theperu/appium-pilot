"""`swipe`, `scroll`, `press`, `hide-keyboard` — gestures and keys."""

from __future__ import annotations

import argparse

from appium_pilot.output import CommandError, emit
from appium_pilot.resolve import find_ref
from appium_pilot.session import Session
from appium_pilot.snapshot import build_snapshot
from appium_pilot.strategies.base import DIRECTIONS


def add_parser(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("swipe", help="swipe the screen in a direction")
    s.add_argument("direction", choices=list(DIRECTIONS) + ["coords"],
                   help="direction, or 'coords' for explicit x1 y1 x2 y2")
    s.add_argument("coords", nargs="*", type=int, help="x1 y1 x2 y2 when direction=coords")
    s.add_argument("--amount", type=float, default=1.0,
                   help="fraction of screen to swipe (default 1.0); ignored for coords")
    s.set_defaults(func=run_swipe)

    sc = sub.add_parser("scroll", help="scroll a ref into view, or scroll to text")
    sc.add_argument("ref", nargs="?", help="ref to scroll into view")
    sc.add_argument("--to", dest="to_text", help="scroll until text is visible")
    sc.set_defaults(func=run_scroll)

    pr = sub.add_parser("press", help="press a hardware/system key (back/home/enter/...)")
    pr.add_argument("key", help="back | home | enter | <android keycode>")
    pr.set_defaults(func=run_press)

    hk = sub.add_parser("hide-keyboard", help="dismiss the on-screen keyboard")
    hk.set_defaults(func=run_hide_keyboard)


def run_swipe(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    if args.direction == "coords":
        if len(args.coords) != 4:
            raise CommandError("coords swipe needs exactly: x1 y1 x2 y2")
        x1, y1, x2, y2 = args.coords
        driver.swipe(x1, y1, x2, y2, 400)
        emit(f"swiped ({x1},{y1})->({x2},{y2})")
        return
    session.strategy.swipe(driver, args.direction, args.amount)
    emit(f"swiped {args.direction}")


def run_scroll(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    strategy = session.strategy

    if args.to_text:
        element = strategy.scroll_to_text(driver, args.to_text)
        if element is None:
            raise CommandError(f"could not find text {args.to_text!r} by scrolling", code=2)
        # Refresh refs so the now-visible element is addressable.
        _refresh_refs(session, driver)
        emit(f"scrolled to text {args.to_text!r}; refs refreshed")
        return

    if not args.ref:
        raise CommandError("scroll needs a ref or --to <text>")
    locator = session.locator_for(args.ref)
    element = find_ref(driver, locator, args.ref)
    strategy.scroll_to_element(driver, element)
    emit(f"scrolled {args.ref} into view", ref=args.ref)


def run_press(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    session.strategy.press_key(driver, args.key)
    emit(f"pressed {args.key}")


def run_hide_keyboard(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    session.strategy.hide_keyboard(driver)
    emit("keyboard dismissed")


def _refresh_refs(session: Session, driver) -> None:  # noqa: ANN001
    _, refmap = build_snapshot(driver.page_source, session.strategy)
    session.set_refmap(refmap)
    session.save()
