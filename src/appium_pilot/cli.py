"""appium-pilot front-end: global flags, subcommand dispatch, error mapping.

Supports `-s=<name>` session selection (default "default") placed anywhere
before the subcommand.
"""

from __future__ import annotations

import argparse
import os
import sys

from selenium.common.exceptions import WebDriverException

from appium_pilot import __version__
from appium_pilot.commands import (
    alert_cmd,
    app_cmd,
    capture_cmd,
    devices_cmd,
    doctor_cmd,
    expect_cmd,
    gesture_cmd,
    get_cmd,
    open_cmd,
    session_cmd,
    skills_cmd,
    snapshot_cmd,
    tap_cmd,
    type_cmd,
    url_cmd,
    video_cmd,
    wait_cmd,
)
from appium_pilot.output import CommandError, fail, set_json_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="appium-pilot",
        description="Agent-first, session-based CLI for driving mobile apps via Appium.",
    )
    parser.add_argument("-s", "--session", default="default", help="session name (default: default)")
    parser.add_argument("--json", action="store_true", help="emit structured JSON output")
    parser.add_argument("--version", action="version", version=f"appium-pilot {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    for module in (
        open_cmd,
        snapshot_cmd,
        capture_cmd,
        tap_cmd,
        type_cmd,
        get_cmd,
        expect_cmd,
        gesture_cmd,
        wait_cmd,
        url_cmd,
        alert_cmd,
        video_cmd,
        app_cmd,
        devices_cmd,
        session_cmd,
        skills_cmd,
        doctor_cmd,
    ):
        module.add_parser(sub)
    return parser


def _normalize_session_flag(argv: list[str]) -> list[str]:
    """Allow `-s=name` in addition to argparse's `-s name`."""
    out: list[str] = []
    for arg in argv:
        if arg.startswith("-s=") or arg.startswith("--session="):
            out.append("--session")
            out.append(arg.split("=", 1)[1])
        else:
            out.append(arg)
    return out


def main(argv: list[str] | None = None) -> None:
    argv = _normalize_session_flag(list(argv if argv is not None else sys.argv[1:]))
    args = build_parser().parse_args(argv)
    set_json_mode(args.json)

    try:
        args.func(args)
    except CommandError as exc:
        fail(str(exc), code=exc.code, **exc.data)
    except WebDriverException as exc:
        # Driver-level failures (e.g. an action the app/platform rejects) become a
        # clean one-line error, not a traceback. Set APPIUM_PILOT_DEBUG=1 to see it.
        if os.environ.get("APPIUM_PILOT_DEBUG"):
            raise
        msg = (getattr(exc, "msg", None) or str(exc)).strip().splitlines()[0]
        fail(f"driver error: {msg}")
    except KeyboardInterrupt:
        fail("interrupted", code=130)


if __name__ == "__main__":
    main()
