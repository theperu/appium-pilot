"""`url` — open a deep link / URL to jump straight to a screen.

A common shortcut past several taps of navigation. On Android this fires a
deep-link intent at the app under test (`mobile: deepLink`); on iOS the system
routes the URL by scheme (custom scheme → the app, http(s) → Safari).
"""

from __future__ import annotations

import argparse

from appium_pilot.output import emit
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("url", help="open a deep link / URL (e.g. myapp://profile/42)")
    p.add_argument("url", help="the deep link or URL to open")
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    session.strategy.open_url(driver, args.url, session.app_id)
    emit(f"opened {args.url}", url=args.url)
