"""`snapshot` — capture the screen as filtered XML and refresh the ref map."""

from __future__ import annotations

import argparse

from appium_pilot.output import emit, raw
from appium_pilot.session import Session
from appium_pilot.snapshot import build_snapshot


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("snapshot", help="capture the current screen + element refs")
    p.add_argument("--raw", action="store_true", help="dump full unfiltered page source")
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    page_source = driver.page_source

    if args.raw:
        raw(page_source)
        return

    xml, refmap = build_snapshot(page_source, session.strategy)
    session.set_refmap(refmap)
    session.save()

    if not refmap:
        emit("snapshot captured 0 meaningful elements (try --raw to inspect)", count=0)
        return

    raw(xml)
