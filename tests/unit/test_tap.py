"""Richer `tap` (§2.2): coordinate parsing + per-platform gesture dispatch."""

import pytest

from appium_pilot.commands.tap_cmd import _parse_xy
from appium_pilot.output import CommandError
from appium_pilot.strategies import get_strategy

AND = get_strategy("android")
IOS = get_strategy("ios")


class _El:
    id = "E1"


class _Drv:
    def __init__(self):
        self.calls = []

    def execute_script(self, name, args):
        self.calls.append((name, args))


# --- coordinate parsing ----------------------------------------------------

@pytest.mark.parametrize("spec,expected", [
    ("200,640", (200, 640)),
    ("200, 640", (200, 640)),
    (" 0,0 ", (0, 0)),
])
def test_parse_xy_ok(spec, expected):
    assert _parse_xy(spec) == expected


@pytest.mark.parametrize("spec", ["200", "a,b", "1,2,3", ""])
def test_parse_xy_rejects_bad(spec):
    with pytest.raises(CommandError):
        _parse_xy(spec)


# --- gesture dispatch ------------------------------------------------------

def test_android_gestures():
    d = _Drv()
    AND.gesture_tap(d, "single", x=1, y=2)
    AND.gesture_tap(d, "long", element=_El(), duration=2.0)
    AND.gesture_tap(d, "double", element=_El())
    assert d.calls == [
        ("mobile: clickGesture", {"x": 1, "y": 2}),
        ("mobile: longClickGesture", {"elementId": "E1", "duration": 2000}),  # seconds→ms
        ("mobile: doubleClickGesture", {"elementId": "E1"}),
    ]


def test_ios_gestures():
    d = _Drv()
    IOS.gesture_tap(d, "single", x=1, y=2)
    IOS.gesture_tap(d, "long", element=_El(), duration=2.0)
    IOS.gesture_tap(d, "double", element=_El())
    assert d.calls == [
        ("mobile: tap", {"x": 1, "y": 2}),
        ("mobile: touchAndHold", {"elementId": "E1", "duration": 2.0}),  # seconds
        ("mobile: doubleTap", {"elementId": "E1"}),
    ]
