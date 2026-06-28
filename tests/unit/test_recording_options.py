"""Recording-option divergence: iOS adds videoQuality, Android doesn't."""

from appium_pilot.strategies import get_strategy


def test_ios_includes_video_quality():
    opts = get_strategy("ios").recording_options(120, "high")
    assert opts["timeLimit"] == "120"
    assert opts["videoQuality"] == "high"


def test_android_omits_video_quality():
    opts = get_strategy("android").recording_options(120, "high")
    assert opts["timeLimit"] == "120"
    assert "videoQuality" not in opts
