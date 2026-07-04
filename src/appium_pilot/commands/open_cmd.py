"""`open` — create a session and persist its handle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from appium_pilot import config, devices, server
from appium_pilot.output import CommandError, emit
from appium_pilot.session import Session, new_driver

AUTOMATION = {"android": "UiAutomator2", "ios": "XCUITest"}
APP_EXT_PLATFORM = {".apk": "android", ".aab": "android", ".app": "ios", ".ipa": "ios"}


def add_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("open", help="open a session against a device/app")
    p.add_argument("app", nargs="?", help="path to an app artifact (.app/.apk/.ipa)")
    p.add_argument("--platform", choices=["android", "ios"], help="target platform")
    p.add_argument("--device", help="device udid or name (else auto-pick/boot)")
    p.add_argument("--app", dest="app_flag", help="app artifact path (alternative to positional)")
    p.add_argument("--app-package", help="Android appPackage of an installed app to launch")
    p.add_argument("--app-activity", help="Android appActivity (optional)")
    p.add_argument("--bundle-id", help="iOS bundleId of an installed app to launch")
    p.add_argument("--cap", action="append", default=[], metavar="k=v",
                   help="extra capability (repeatable); appium: prefix added if missing")
    p.add_argument("--caps-file", help="JSON file of capabilities to merge")
    p.add_argument("--auto-accept-alerts", action="store_true",
                   help="auto-accept permission/system dialogs "
                        "(autoGrantPermissions on Android, autoAcceptAlerts on iOS)")
    p.set_defaults(func=run)


# Per-platform capability that makes the driver clear permission/system dialogs
# on its own. Android grants runtime permissions; iOS taps the accept button.
AUTO_ACCEPT_ALERT_CAP = {
    "android": {"appium:autoGrantPermissions": True},
    "ios": {"appium:autoAcceptAlerts": True},
}


def _infer_platform(args, app: Optional[str]) -> str:
    if args.platform:
        return args.platform
    if args.bundle_id:
        return "ios"
    if args.app_package or args.app_activity:
        return "android"
    if app:
        ext = Path(app).suffix.lower()
        if ext in APP_EXT_PLATFORM:
            return APP_EXT_PLATFORM[ext]
    raise CommandError("could not infer platform; pass --platform android|ios")


def _parse_caps(pairs: list[str]) -> dict:
    caps: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise CommandError(f"bad --cap {pair!r}; expected key=value")
        key, value = pair.split("=", 1)
        if ":" not in key and key not in ("platformName",):
            key = f"appium:{key}"
        caps[key] = _coerce(value)
    return caps


def _coerce(value: str):
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if value.isdigit():
        return int(value)
    return value


def run(args) -> None:
    app = args.app_flag or args.app
    platform = _infer_platform(args, app)
    strategy_automation = AUTOMATION[platform]

    device = devices.resolve(platform, args.device)

    caps: dict = {
        "platformName": "Android" if platform == "android" else "iOS",
        "appium:automationName": strategy_automation,
        "appium:udid": device.udid,
        "appium:deviceName": device.name,
        "appium:newCommandTimeout": config.NEW_COMMAND_TIMEOUT,
    }
    if app:
        caps["appium:app"] = str(Path(app).expanduser().resolve())
    if args.app_package:
        caps["appium:appPackage"] = args.app_package
    if args.app_activity:
        caps["appium:appActivity"] = args.app_activity
    if args.bundle_id:
        caps["appium:bundleId"] = args.bundle_id

    if args.auto_accept_alerts:
        caps.update(AUTO_ACCEPT_ALERT_CAP[platform])

    if args.caps_file:
        caps.update(json.loads(Path(args.caps_file).read_text()))
    caps.update(_parse_caps(args.cap))  # explicit --cap / caps-file win

    base_url = server.ensure_server()
    driver = new_driver(base_url, caps)

    session = Session(
        name=args.session,
        server_url=base_url,
        session_id=driver.session_id,
        platform=platform,
        device=device.udid,
        caps=caps,
    )
    session.save()

    emit(
        f"opened session '{args.session}' on {platform} ({device.name}). Run `snapshot` next.",
        session=args.session,
        platform=platform,
        device=device.udid,
        session_id=driver.session_id,
    )
