"""open command helpers: platform inference, capability parsing, coercion."""

import argparse

import pytest

from appium_pilot.commands.open_cmd import _coerce, _infer_platform, _parse_caps
from appium_pilot.output import CommandError


def _args(**kw):
    base = dict(platform=None, bundle_id=None, app_package=None, app_activity=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_infer_explicit_platform():
    assert _infer_platform(_args(platform="ios"), None) == "ios"


def test_infer_from_bundle_id():
    assert _infer_platform(_args(bundle_id="com.x"), None) == "ios"


def test_infer_from_app_package():
    assert _infer_platform(_args(app_package="com.x"), None) == "android"


def test_infer_from_extension():
    assert _infer_platform(_args(), "/p/My.apk") == "android"
    assert _infer_platform(_args(), "/p/My.app") == "ios"
    assert _infer_platform(_args(), "/p/My.ipa") == "ios"


def test_infer_missing_raises():
    with pytest.raises(CommandError):
        _infer_platform(_args(), None)


def test_parse_caps_adds_appium_prefix():
    caps = _parse_caps(["noReset=true", "appium:foo=bar", "platformName=iOS"])
    assert caps["appium:noReset"] is True       # prefixed + coerced
    assert caps["appium:foo"] == "bar"          # already namespaced, left alone
    assert caps["platformName"] == "iOS"        # the one allowed bare key


def test_parse_caps_bad_pair_raises():
    with pytest.raises(CommandError):
        _parse_caps(["bogus"])


def test_coerce_types():
    assert _coerce("true") is True
    assert _coerce("false") is False
    assert _coerce("42") == 42
    assert _coerce("hello") == "hello"
