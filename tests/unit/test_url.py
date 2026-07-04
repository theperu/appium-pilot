"""Deep-link `url` command (§2.4): per-platform open_url dispatch."""

import pytest

from appium_pilot.output import CommandError
from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")


class _Drv:
    def __init__(self):
        self.scripts = []
        self.got = None

    def execute_script(self, name, args):
        self.scripts.append((name, args))

    def get(self, url):
        self.got = url


def test_android_open_url_fires_deeplink_with_package():
    d = _Drv()
    AND.open_url(d, "myapp://x/1", app_id="com.example.app")
    assert d.scripts == [("mobile: deepLink", {"url": "myapp://x/1", "package": "com.example.app"})]


def test_android_open_url_requires_package():
    with pytest.raises(CommandError):
        AND.open_url(_Drv(), "myapp://x/1", app_id=None)


def test_ios_open_url_uses_driver_get():
    d = _Drv()
    IOS.open_url(d, "https://example.com", app_id="io.appium.TestApp")
    assert d.got == "https://example.com"
    assert d.scripts == []  # iOS routes by scheme via the system, not deepLink
