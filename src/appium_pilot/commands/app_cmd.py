"""App lifecycle (`launch`/`terminate`/`activate`/`background`/`install`/`remove`/`reset`)
and `orientation`."""

from __future__ import annotations

import argparse
from pathlib import Path

from appium_pilot.output import CommandError, emit
from appium_pilot.session import Session


def add_parser(sub: argparse._SubParsersAction) -> None:
    for name, help_text in [
        ("launch", "activate (foreground) the app under test"),
        ("activate", "activate (foreground) the app under test"),
        ("terminate", "terminate the app under test"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("app_id", nargs="?", help="app id (default: the session's app)")
        p.set_defaults(func=_make_lifecycle(name))

    bg = sub.add_parser("background", help="background the app for N seconds (-1 = indefinitely)")
    bg.add_argument("seconds", nargs="?", type=int, default=-1)
    bg.set_defaults(func=run_background)

    inst = sub.add_parser("install", help="install an app artifact on the device")
    inst.add_argument("path", help="path to .apk/.app/.ipa")
    inst.set_defaults(func=run_install)

    rm = sub.add_parser("remove", help="uninstall an app from the device")
    rm.add_argument("app_id", nargs="?", help="app id (default: the session's app)")
    rm.set_defaults(func=run_remove)

    rs = sub.add_parser("reset", help="terminate then re-activate the app under test")
    rs.set_defaults(func=run_reset)

    o = sub.add_parser("orientation", help="get or set screen orientation")
    o.add_argument("value", nargs="?", choices=["portrait", "landscape"],
                   help="omit to read the current orientation")
    o.set_defaults(func=run_orientation)


def _app_id(session: Session, explicit: str | None) -> str:
    app_id = explicit or session.app_id
    if not app_id:
        raise CommandError("no app id known for this session; pass one explicitly")
    return app_id


def _make_lifecycle(action: str):
    def run(args) -> None:
        session = Session.load(args.session)
        driver = session.attach()
        app_id = _app_id(session, args.app_id)
        if action in ("launch", "activate"):
            driver.activate_app(app_id)
            emit(f"activated {app_id}", app=app_id)
        elif action == "terminate":
            driver.terminate_app(app_id)
            emit(f"terminated {app_id}", app=app_id)

    return run


def run_background(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    driver.background_app(args.seconds)
    emit(f"backgrounded app for {args.seconds}s")


def run_install(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    path = str(Path(args.path).expanduser().resolve())
    driver.install_app(path)
    emit(f"installed {path}", path=path)


def run_remove(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    app_id = _app_id(session, args.app_id)
    driver.remove_app(app_id)
    emit(f"removed {app_id}", app=app_id)


def run_reset(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    app_id = _app_id(session, None)
    driver.terminate_app(app_id)
    driver.activate_app(app_id)
    emit(f"reset {app_id}", app=app_id)


def run_orientation(args) -> None:
    session = Session.load(args.session)
    driver = session.attach()
    if args.value:
        driver.orientation = args.value.upper()
        emit(f"orientation set to {args.value}", orientation=args.value.upper())
    else:
        current = driver.orientation
        emit(current, orientation=current)
