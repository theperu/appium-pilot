"""Session persistence + ref→locator resolution (stale/unknown → exit 2)."""

import pytest

from appium_pilot import config
from appium_pilot.output import CommandError
from appium_pilot.session import Session
from appium_pilot.strategies import Locator


@pytest.fixture
def sess_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    return tmp_path


def _make():
    return Session(
        name="default", server_url="http://127.0.0.1:4723",
        session_id="sid-123", platform="android", device="emulator-5554",
    )


def test_roundtrip(sess_dir):
    s = _make()
    s.caps = {"platformName": "Android", "appium:appPackage": "com.x"}
    s.save()
    loaded = Session.load("default")
    assert loaded.session_id == "sid-123"
    assert loaded.platform == "android"
    assert loaded.app_id == "com.x"


def test_refmap_roundtrip(sess_dir):
    s = _make()
    s.set_refmap({"e1": Locator("id", "com.x:id/login", "Log in")})
    s.save()
    loc = Session.load("default").locator_for("e1")
    assert loc.by == "id" and loc.value == "com.x:id/login" and loc.text == "Log in"


def test_unknown_ref_raises_code_2(sess_dir):
    s = _make()
    s.save()
    with pytest.raises(CommandError) as exc:
        s.locator_for("e999")
    assert exc.value.code == 2


def test_load_missing_session_raises(sess_dir):
    with pytest.raises(CommandError):
        Session.load("nope")
