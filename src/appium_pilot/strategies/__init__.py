"""Platform strategy registry."""

from __future__ import annotations

from appium_pilot.output import CommandError
from appium_pilot.strategies.android import AndroidStrategy
from appium_pilot.strategies.base import Locator, PlatformStrategy
from appium_pilot.strategies.ios import IOSStrategy

__all__ = ["Locator", "PlatformStrategy", "get_strategy"]


def get_strategy(platform: str) -> PlatformStrategy:
    p = platform.lower()
    if p == "android":
        return AndroidStrategy()
    if p == "ios":
        return IOSStrategy()
    raise CommandError(f"unsupported platform: {platform!r} (expected 'android' or 'ios')")
