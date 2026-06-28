"""`wait` — explicit synchronization on a ref, on text, or on disappearance."""

from __future__ import annotations

import argparse

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from appium_pilot.output import CommandError, emit
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("wait", help="wait for a ref/text to appear, or a ref to disappear")
    p.add_argument("ref", nargs="?", help="ref to wait for (present)")
    p.add_argument("--text", dest="text", help="wait until an element with this text appears")
    p.add_argument("--gone", dest="gone_ref", help="wait until this ref's element disappears")
    p.add_argument("--timeout", type=float, default=10.0, help="seconds (default 10)")
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    # Disable implicit wait so the explicit polling controls timing.
    driver.implicitly_wait(0)
    wait = WebDriverWait(driver, timeout=args.timeout, poll_frequency=0.3)

    try:
        if args.gone_ref:
            locator = session.locator_for(args.gone_ref)
            wait.until_not(lambda d: d.find_elements(by=locator.by, value=locator.value))
            emit(f"{args.gone_ref} gone", ref=args.gone_ref)
        elif args.text:
            wait.until(lambda d: session.strategy.find_by_text(d, args.text))
            emit(f"text {args.text!r} present", text=args.text)
        elif args.ref:
            locator = session.locator_for(args.ref)
            wait.until(lambda d: d.find_elements(by=locator.by, value=locator.value))
            emit(f"{args.ref} present", ref=args.ref)
        else:
            raise CommandError("wait needs a ref, --text, or --gone")
    except TimeoutException as exc:
        raise CommandError(f"wait timed out after {args.timeout}s", code=2) from exc
