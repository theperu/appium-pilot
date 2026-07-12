"""Sample-app sourcing + per-platform scenario models for the E2E suite.

Android: prebuilt ApiDemos APK (pinned release + sha256).
iOS: TestApp built from source with xcodebuild (cached). Both skip cleanly if
their toolchain/network is unavailable.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

APPS_DIR = Path(__file__).parent.parent / "_apps"

ANDROID_APK_URL = "https://github.com/appium/android-apidemos/releases/download/v6.0.11/ApiDemos-debug.apk"
ANDROID_APK_SHA256 = "adfa06ab73b1e943dd405a78fd422c3ef9438111d15d7ce392bef6d03cc5fc36"
IOS_REPO = "https://github.com/appium/ios-test-app"


def _ensure_android_apk() -> Path:
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    apk = APPS_DIR / "ApiDemos.apk"
    if not apk.exists():
        try:
            urllib.request.urlretrieve(ANDROID_APK_URL, apk)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"cannot download ApiDemos.apk: {exc}")
        if hashlib.sha256(apk.read_bytes()).hexdigest() != ANDROID_APK_SHA256:
            apk.unlink()
            pytest.skip("ApiDemos.apk sha256 mismatch")
    return apk


def _ensure_ios_app() -> Path:
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    app = APPS_DIR / "TestApp.app"
    if app.exists():
        return app
    if not (shutil.which("xcodebuild") and shutil.which("git")):
        pytest.skip("xcodebuild/git unavailable to build iOS TestApp")
    src = APPS_DIR / "ios-test-app-src"
    build = APPS_DIR / "ios-test-app-build"
    try:
        if not src.exists():
            subprocess.run(["git", "clone", "--depth", "1", IOS_REPO, str(src)],
                           check=True, capture_output=True)
        subprocess.run(
            ["xcodebuild", "-project", str(src / "TestApp.xcodeproj"), "-scheme", "TestApp",
             "-sdk", "iphonesimulator", "-configuration", "Debug",
             "-derivedDataPath", str(build), "CODE_SIGNING_ALLOWED=NO", "build"],
            check=True, capture_output=True,
        )
        shutil.copytree(build / "Build/Products/Debug-iphonesimulator/TestApp.app", app)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"iOS TestApp build failed: {exc}")
    return app


class AndroidApp:
    platform = "android"
    app_id = "io.appium.android.apis"
    ready_text = "Views"
    scroll_target = "Views"

    def artifact(self) -> Path:
        return _ensure_android_apk()

    def open_args(self, artifact: Path) -> list[str]:
        # The quoted pilotProbe cap exercises the --cap force-string escape hatch
        # (test_quoted_cap_persisted_as_string); it's a harmless unknown vendor cap.
        return ["open", "--platform", "android", "--app", str(artifact),
                "--app-package", self.app_id, "--cap", 'appium:pilotProbe="17"']

    def ready_ref(self, cli) -> str:
        return cli.ref_for(r'(text|desc)="Views"')

    def reach_editable(self, cli) -> str:
        cli.run("tap", cli.ref_for(r'(text|desc)="Views"'))
        cli.run("wait", "--text", "Controls", "--timeout", "10")
        cli.run("tap", cli.ref_for(r'(text|desc)="Controls"'))
        cli.run("wait", "--text", "Light Theme", "--timeout", "10")
        cli.run("tap", cli.ref_for(r'text="1\. Light Theme"'))
        cli.run("wait", "--text", "hint text", "--timeout", "10")
        # Snapshot ids are shown package-stripped (io.appium.android.apis:id/edit -> edit).
        return cli.ref_for(r'id="edit"')

    type_value = "hello"

    def tap_check(self, cli) -> str:
        """Perform a tap that changes screen; return text expected afterwards."""
        cli.run("tap", cli.ref_for(r'(text|desc)="Views"'))
        return "Buttons"  # an item in the Views submenu

    def find_case(self, cli) -> tuple[str, str]:
        """A query unique to one element + that element's snapshot ref, to prove
        `find` returns the same ref (full-screen numbering) and it's actionable."""
        return "Views", cli.ref_for(r'(text|desc)="Views"')

    # wait --gone: tap into Views so a root-only item disappears
    # ("Preference" exists on the root list but not inside the Views submenu).
    def disappearing_ref(self, cli) -> str:
        return cli.ref_for(r'(text|desc)="Preference"')

    def cause_disappear(self, cli) -> None:
        cli.run("tap", cli.ref_for(r'(text|desc)="Views"'))

    def show_alert(self, cli):
        """Raise a system dialog; return an expected substring of its text (or
        None if the trigger isn't found). App > Alert Dialogs > OK-Cancel."""
        if cli.run("tap", "--text", "App", check=False)[0] != 0:
            return None
        cli.run("wait", "--text", "Alert Dialogs", "--timeout", "8", check=False)
        cli.run("tap", "--text", "Alert Dialogs", check=False)
        cli.run("wait", "--text", "OK Cancel dialog with a message", "--timeout", "8", check=False)
        if cli.run("tap", "--text", "OK Cancel dialog with a message", check=False)[0] != 0:
            return None
        cli.run("wait", "--text", "Lorem", "--timeout", "8", check=False)
        return "Lorem ipsum"


class IOSApp:
    platform = "ios"
    app_id = "io.appium.TestApp"
    ready_text = "Compute Sum"
    scroll_target = "Crash"

    def artifact(self) -> Path:
        return _ensure_ios_app()

    def open_args(self, artifact: Path) -> list[str]:
        # See AndroidApp.open_args re: the quoted pilotProbe force-string cap.
        return ["open", "--platform", "ios", "--app", str(artifact),
                "--bundle-id", self.app_id, "--cap", 'appium:pilotProbe="17"']

    def ready_ref(self, cli) -> str:
        return cli.ref_for(r'name="IntegerA"')

    def reach_editable(self, cli) -> str:
        return cli.ref_for(r'name="IntegerA"')

    type_value = "246"

    def tap_check(self, cli) -> str:
        cli.run("type", cli.ref_for(r'name="IntegerA"'), "2")
        cli.run("type", cli.ref_for(r'name="IntegerB"'), "3")
        cli.run("tap", cli.ref_for(r'name="ComputeSumButton"'))
        return "5"  # Answer label becomes the sum

    def find_case(self, cli) -> tuple[str, str]:
        """See AndroidApp.find_case. IntegerA is a unique, tappable field."""
        return "IntegerA", cli.ref_for(r'name="IntegerA"')

    # No reliably-disappearing element in TestApp's single screen.
    def disappearing_ref(self, cli):
        return None

    def cause_disappear(self, cli) -> None:
        pass

    def show_alert(self, cli):
        """TestApp's "show alert" button raises an alert titled "Cool title"."""
        if cli.run("tap", "--text", "show alert", check=False)[0] != 0:
            return None
        cli.run("wait", "--text", "cool", "--timeout", "8", check=False)
        return "cool"


def get_app(platform: str):
    return AndroidApp() if platform == "android" else IOSApp()
