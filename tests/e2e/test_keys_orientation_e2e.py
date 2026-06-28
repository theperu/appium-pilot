"""E2E: hardware/system keys and orientation."""

import pytest

pytestmark = pytest.mark.e2e


def test_press_home(fresh, app):
    assert fresh.run("press", "home", check=False)[0] == 0
    fresh.run("activate", app.app_id, check=False)


def test_press_back(fresh, app):
    rc = fresh.run("press", "back", check=False)[0]
    if app.platform == "android":
        assert rc == 0
    else:
        assert rc != 0  # iOS has no system back; must error cleanly


def test_press_enter_android(fresh, app):
    if app.platform != "android":
        pytest.skip("iOS press-enter (mobile: keys) is driver-fragile; covered manually")
    assert fresh.run("press", "enter", check=False)[0] == 0


def test_orientation_get(fresh):
    rc, out, _ = fresh.run("orientation")
    assert rc == 0 and out.strip().upper() in {"PORTRAIT", "LANDSCAPE"}


def test_orientation_set(fresh, app):
    if app.platform != "android":
        pytest.skip("TestApp does not rotate reliably on iPhone")
    assert fresh.run("orientation", "landscape")[0] == 0
    assert fresh.run("orientation")[1].strip().upper() == "LANDSCAPE"
    fresh.run("orientation", "portrait")
