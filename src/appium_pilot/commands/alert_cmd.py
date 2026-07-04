"""`alert` — read, accept, or dismiss a system alert / permission dialog.

System popups ("Allow notifications?", crash dialogs) block real flows and are
not part of the app's own view hierarchy, so refs don't reach them. This drives
the W3C alert channel instead. To skip permission prompts entirely at launch,
see `open --auto-accept-alerts`.
"""

from __future__ import annotations

import argparse

from appium_pilot.output import CommandError, emit
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("alert", help="read/accept/dismiss a system alert or permission dialog")
    p.add_argument(
        "action", nargs="?", choices=["accept", "dismiss"],
        help="accept or dismiss the alert; omit to just print its text",
    )
    p.set_defaults(func=run)


def run(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    strategy = session.strategy

    # Capture the text first so the confirmation names the dialog that was acted on.
    text = strategy.alert_text(driver)
    if text is None:
        raise CommandError("no alert is currently shown", code=2)

    if args.action == "accept":
        strategy.accept_alert(driver)
        emit(f"alert accepted: {text}", action="accept", text=text)
    elif args.action == "dismiss":
        strategy.dismiss_alert(driver)
        emit(f"alert dismissed: {text}", action="dismiss", text=text)
    else:
        emit(text, text=text)
